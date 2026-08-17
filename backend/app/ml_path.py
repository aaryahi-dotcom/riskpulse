"""
Adds the sibling ml/ directory to sys.path so backend modules can import
`feature_registry` and `puppet_signals` directly — the single source of
truth for the feature list and the puppet-score formula stays in ml/,
shared by both the training script and the live API, per the monorepo
layout (backend/ and ml/ are siblings, not nested packages). Import this
module (for its side effect) before importing anything from ml/.
"""
from __future__ import annotations

import os
import sys

_BACKEND_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_DIR = os.path.normpath(os.path.join(_BACKEND_APP_DIR, "..", "..", "ml"))

if _ML_DIR not in sys.path:
    sys.path.insert(0, _ML_DIR)
