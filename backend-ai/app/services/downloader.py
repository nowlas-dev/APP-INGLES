"""
LingoBeats — backend-ai/app/services/downloader.py
Mapeo canónico a audio_engine.services.downloader
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from audio_engine.services.downloader import AudioDownloader, ALLOWED_DOMAINS

__all__ = ["AudioDownloader", "ALLOWED_DOMAINS"]
