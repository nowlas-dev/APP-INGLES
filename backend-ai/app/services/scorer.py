"""
LingoBeats — backend-ai/app/services/scorer.py
Mapeo canónico a audio_engine.services.scorer
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from audio_engine.services.scorer import PhoneticScorer

__all__ = ["PhoneticScorer"]
