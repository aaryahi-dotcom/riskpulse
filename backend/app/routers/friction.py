"""
Friction Agent endpoints (Stage 2).

POST /api/v1/friction/start/{txn_id} — Start conversation, return first question.
POST /api/v1/friction/{session_id}/answer — Submit answer, get next question or completion.
GET /api/v1/friction/{session_id} — Retrieve session state.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.friction import MockFrictionAgent
from ..db import get_db
from ..models_db import FrictionSession
from ..schemas import FrictionAnswerRequest, FrictionAnswerResponse, FrictionResponse
from ..security import get_current_subject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/friction", tags=["friction"])


@router.post("/start/{txn_id}", response_model=FrictionResponse)
def start_friction_conversation(
    txn_id: str,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
    scam_type: str | None = None,
    language: str = "en",
) -> FrictionResponse:
    """Start a Friction Agent conversation for a transaction.

    Creates a new FrictionSession and returns the first question.
    """
    # Check if session already exists for this txn_id
    existing = db.query(FrictionSession).filter(FrictionSession.txn_id == txn_id).first()
    if existing is not None:
        return FrictionResponse(
            session_id=existing.id,
            status=existing.status,
            turn_count=existing.turn_count,
            max_turns=existing.max_turns,
            current_question=existing.current_question,
            current_options=existing.current_options,
            conversation_history=[],  # TODO: reconstruct from JSON
            coercion_likelihood=existing.coercion_likelihood,
            key_answers=existing.key_answers,
            reasoning=existing.reasoning,
        )

    # Create new session
    agent = MockFrictionAgent(scam_type=scam_type, language=language, max_turns=4)
    result = agent.start_conversation()

    session = FrictionSession(
        txn_id=txn_id,
        sender_id="",  # Not available here; could be passed in payload
        status=result["status"],
        turn_count=result["turn_count"],
        current_question=result.get("current_question"),
        current_options=result.get("current_options", []),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(f"Started Friction session {session.id} for txn {txn_id}")

    return FrictionResponse(
        session_id=session.id,
        status=session.status,
        turn_count=session.turn_count,
        max_turns=session.max_turns,
        current_question=session.current_question,
        current_options=session.current_options,
        conversation_history=[],
        coercion_likelihood=session.coercion_likelihood,
        key_answers=session.key_answers,
        reasoning=session.reasoning,
    )


@router.post("/{session_id}/answer", response_model=FrictionAnswerResponse)
def submit_friction_answer(
    session_id: str,
    payload: FrictionAnswerRequest,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> FrictionAnswerResponse:
    """Submit an answer to the current friction question.

    Returns the next question or completion.
    """
    session = db.query(FrictionSession).filter(FrictionSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Friction session not found")

    if session.status == "completed":
        return FrictionAnswerResponse(
            session_id=session.id,
            status=session.status,
            turn_count=session.turn_count,
            max_turns=session.max_turns,
            current_question=None,
            current_options=None,
            coercion_likelihood=session.coercion_likelihood,
            key_answers=session.key_answers,
            reasoning=session.reasoning,
        )

    # Recreate agent and restore conversation state
    scam_type = None  # TODO: could store in session
    language = payload.language
    agent = MockFrictionAgent(scam_type=scam_type, language=language, max_turns=session.max_turns)

    # Replay conversation history to restore state
    conversation = session.conversation_json if isinstance(session.conversation_json, list) else []
    for turn in conversation:
        agent.conversation.append(turn)
        agent.coercion_scores.append(turn.get("coercion_score", 0.0))
    agent.turn_count = session.turn_count

    # Process new answer
    result = agent.process_answer(payload.answer)

    # Update session
    session.status = result["status"]
    session.turn_count = result["turn_count"]
    session.current_question = result.get("current_question")
    session.current_options = result.get("current_options", [])
    session.coercion_likelihood = result.get("coercion_likelihood", session.coercion_likelihood)
    session.key_answers = result.get("key_answers", session.key_answers)
    session.reasoning = result.get("reasoning", session.reasoning)
    session.conversation_json = agent.conversation

    db.commit()
    db.refresh(session)

    logger.info(f"Friction session {session_id}: turn {session.turn_count}, status {session.status}")

    return FrictionAnswerResponse(
        session_id=session.id,
        status=session.status,
        turn_count=session.turn_count,
        max_turns=session.max_turns,
        current_question=session.current_question,
        current_options=session.current_options,
        coercion_likelihood=session.coercion_likelihood,
        key_answers=session.key_answers,
        reasoning=session.reasoning,
    )


@router.get("/{session_id}", response_model=FrictionResponse)
def get_friction_session(
    session_id: str,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
) -> FrictionResponse:
    """Retrieve friction session state."""
    session = db.query(FrictionSession).filter(FrictionSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Friction session not found")

    # Reconstruct conversation history from JSON
    conversation_history = []
    if isinstance(session.conversation_json, list):
        for turn_data in session.conversation_json:
            conversation_history.append(
                {
                    "turn": turn_data.get("turn"),
                    "question": turn_data.get("question"),
                    "options": turn_data.get("options"),
                    "answer": turn_data.get("answer"),
                }
            )

    return FrictionResponse(
        session_id=session.id,
        status=session.status,
        turn_count=session.turn_count,
        max_turns=session.max_turns,
        current_question=session.current_question,
        current_options=session.current_options,
        conversation_history=conversation_history,
        coercion_likelihood=session.coercion_likelihood,
        key_answers=session.key_answers,
        reasoning=session.reasoning,
    )
