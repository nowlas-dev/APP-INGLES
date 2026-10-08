"""
LingoBeats — backend-ai/app/services/audio_separator.py
Mapeo canónico a audio_engine.services.audio_separator
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from audio_engine.services.audio_separator import StemSeparator

__all__ = ["StemSeparator"]
