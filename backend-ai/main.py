"""
LingoBeats — backend-ai/main.py
Mapeo canónico hacia audio_engine.main:app
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from audio_engine.main import app

__all__ = ["app"]
