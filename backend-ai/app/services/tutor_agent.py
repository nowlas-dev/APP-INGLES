"""
LingoBeats — backend-ai/app/services/tutor_agent.py
Mapeo canónico a audio_engine.services.tutor_agent
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from audio_engine.services.tutor_agent import TutorAgent, TutorOutputSchema

__all__ = ["TutorAgent", "TutorOutputSchema"]
