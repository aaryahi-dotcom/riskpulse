"""
Friction Agent — adaptive multi-turn conversation to detect user coercion.

Asks the user 3-4 questions (configurable) tailored to suspected scam type.
Each answer feeds into the next question selection. Final output: coercion_likelihood.

Mock mode: returns pre-written questions + simulates user answers for demo.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Question Bank (EN/HI, categorized by scam type)
# ============================================================================

QUESTIONS_EN = {
    "generic": [
        "Is someone on a call or video call with you right now asking you to make this payment?",
        "Were you told to keep this payment secret from your family, bank, or anyone else?",
        "Were you told you need to act urgently or immediately?",
        "Were you promised a refund, reward, or returns if you pay?",
    ],
    "digital_arrest": [
        "Did someone say you are under investigation, arrest, or legal action?",
        "Did someone claim to be from police, CBI, customs, or other authority?",
        "Were you told your account or bank details are compromised or under investigation?",
        "Were you threatened with legal consequences if you don't pay?",
    ],
    "fake_kyc": [
        "Were you told your account will be blocked or frozen?",
        "Did someone ask you to verify your identity through a link or by paying?",
        "Were you told there's a security issue with your account that requires immediate action?",
        "Did you receive an unexpected SMS or email asking you to confirm personal details?",
    ],
    "sextortion": [
        "Were you threatened with sharing private or intimate content/videos?",
        "Did someone claim to have compromising material about you?",
        "Were you blackmailed or threatened unless you pay?",
        "Did someone pretend to be romantically interested in you before asking for money?",
    ],
}

QUESTIONS_HI = {
    "generic": [
        "क्या कोई आपको कॉल या वीडियो कॉल पर यह भुगतान करने के लिए कह रहा है?",
        "क्या आपको अपने परिवार, बैंक या किसी और को इस भुगतान के बारे में बताने से मना किया गया?",
        "क्या आपको तुरंत या तुरंत कार्य करने के लिए कहा गया?",
        "क्या आपको रिफंड, पुरस्कार या रिटर्न का वादा किया गया था?",
    ],
    "digital_arrest": [
        "क्या किसी ने कहा कि आप जांच, गिरफ्तारी या कानूनी कार्रवाई के अधीन हैं?",
        "क्या किसी ने पुलिस, CBI, सीमा शुल्क या अन्य प्राधिकार होने का दावा किया?",
        "क्या आपको बताया गया कि आपका खाता या बैंक विवरण समझौता किया गया है या जांच के अधीन है?",
        "क्या आपको कानूनी परिणामों की धमकी दी गई यदि आप भुगतान नहीं करते हैं?",
    ],
    "fake_kyc": [
        "क्या आपको बताया गया कि आपका खाता ब्लॉक या फ्रीज कर दिया जाएगा?",
        "क्या किसी ने आपको लिंक के माध्यम से या भुगतान करके अपनी पहचान सत्यापित करने के लिए कहा?",
        "क्या आपको बताया गया कि आपके खाते के साथ सुरक्षा समस्या है जिसके लिए तुरंत कार्रवाई की आवश्यकता है?",
        "क्या आपको व्यक्तिगत विवरण की पुष्टि करने के लिए एक अप्रत्याशित SMS या ईमेल प्राप्त हुआ?",
    ],
    "sextortion": [
        "क्या आपको निजी या अंतरंग सामग्री/वीडियो साझा करने की धमकी दी गई?",
        "क्या किसी ने दावा किया कि उसके पास आपके बारे में समझौता करने वाली सामग्री है?",
        "क्या आपको जब तक आप भुगतान नहीं करते तब तक जबरदस्ती या धमकी दी गई?",
        "क्या किसी ने पैसे मांगने से पहले आपके साथ रोमांटिक रूप से दिलचस्पी दिखाई?",
    ],
}


def get_questions_for_scam_type(scam_type: str | None, language: str = "en") -> list[str]:
    """Get question bank for suspected scam type."""
    questions_dict = QUESTIONS_HI if language == "hi" else QUESTIONS_EN

    if not scam_type or scam_type == "none_or_unclear":
        return questions_dict["generic"]

    scam_key = scam_type.lower().replace(" ", "_")
    return questions_dict.get(scam_key, questions_dict["generic"])


# ============================================================================
# Coercion Scoring (Based on Answers)
# ============================================================================

COERCION_KEYWORDS = {
    "police": 0.3,
    "cbi": 0.3,
    "customs": 0.25,
    "arrest": 0.35,
    "investigation": 0.25,
    "secret": 0.2,
    "family": 0.15,
    "urgent": 0.1,
    "block": 0.2,
    "frozen": 0.2,
    "compromise": 0.4,
    "blackmail": 0.35,
    "threaten": 0.3,
    "video": 0.25,
    "intimate": 0.25,
}


def score_answer_for_coercion(answer: str) -> float:
    """Score an answer (0–1) for coercion indicators."""
    if not answer:
        return 0.0

    answer_lower = answer.lower()
    keywords_found = []
    score = 0.0

    for keyword, weight in COERCION_KEYWORDS.items():
        if keyword in answer_lower:
            keywords_found.append(keyword)
            score += weight

    # Cap at 1.0; multiple keywords don't stack infinitely
    score = min(1.0, score)
    return score


# ============================================================================
# Friction Agent Mock Implementation
# ============================================================================

class MockFrictionAgent:
    """Mock Friction Agent for offline demo mode."""

    def __init__(self, scam_type: str | None = None, language: str = "en", max_turns: int = 4):
        self.scam_type = scam_type
        self.language = language
        self.max_turns = max_turns
        self.questions = get_questions_for_scam_type(scam_type, language)
        self.conversation: list[dict[str, Any]] = []
        self.turn_count = 0
        self.coercion_scores: list[float] = []

    def start_conversation(self) -> dict[str, Any]:
        """Start the conversation; return first question + options."""
        self.turn_count = 0
        if self.turn_count < len(self.questions):
            question = self.questions[self.turn_count]
            self.turn_count += 1
            return {
                "status": "in_progress",
                "turn_count": self.turn_count,
                "current_question": question,
                "current_options": ["Yes", "No", "Not sure"],
            }
        return {"status": "completed", "turn_count": self.turn_count}

    def process_answer(self, answer: str) -> dict[str, Any]:
        """Process user answer; advance to next question or complete."""
        if self.turn_count == 0:
            return {"error": "Conversation not started"}

        # Score this answer for coercion signals
        coercion_score = score_answer_for_coercion(answer)
        self.coercion_scores.append(coercion_score)

        # Store turn in history
        self.conversation.append({
            "turn": self.turn_count,
            "question": self.questions[self.turn_count - 1] if self.turn_count <= len(self.questions) else None,
            "answer": answer,
            "coercion_score": coercion_score,
        })

        # Check if we've asked all questions or reached max turns
        if self.turn_count >= self.max_turns or self.turn_count >= len(self.questions):
            return self._finalize_conversation()

        # Ask next question
        if self.turn_count < len(self.questions):
            question = self.questions[self.turn_count]
            self.turn_count += 1
            return {
                "status": "in_progress",
                "turn_count": self.turn_count,
                "current_question": question,
                "current_options": ["Yes", "No", "Not sure"],
            }

        # Fallback (shouldn't reach here)
        return self._finalize_conversation()

    def _finalize_conversation(self) -> dict[str, Any]:
        """Finalize conversation; compute coercion_likelihood and key_answers."""
        if not self.coercion_scores:
            coercion_likelihood = 0.0
        else:
            coercion_likelihood = sum(self.coercion_scores) / len(self.coercion_scores)

        # Identify key answers (those with high coercion scores)
        key_answers = [
            turn["answer"]
            for turn in self.conversation
            if turn.get("coercion_score", 0) > 0.15
        ]

        reasoning = (
            f"Based on {len(self.conversation)} question(s), coercion likelihood is "
            f"{coercion_likelihood:.1%}. High-risk indicators: {', '.join(key_answers[:2]) if key_answers else 'none'}."
        )

        return {
            "status": "completed",
            "turn_count": self.turn_count,
            "coercion_likelihood": round(coercion_likelihood, 2),
            "key_answers": key_answers,
            "reasoning": reasoning,
        }
