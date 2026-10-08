"""
Automated unit & integration test suite for LingoBeats Python AI backend.
"""
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from audio_engine.services.scorer import PhoneticScorer
from audio_engine.services.tutor_agent import TutorAgent
from audio_engine.services.downloader import AudioDownloader
from audio_engine.main import validate_audio_magic_bytes

def test_scorer():
    scorer = PhoneticScorer(passing_threshold=70.0)
    res_exact = scorer.score("Never gonna give you up", "Never gonna give you up")
    assert res_exact["wer"] == 0.0
    assert res_exact["accuracy_score"] == 100.0
    assert res_exact["passed"] is True

    res_omitted = scorer.score("This land is dark and cold", "This lan is dar and col")
    types = [d["type"] for d in res_omitted["discrepancies"]]
    assert "dropped_final_consonant" in types

def test_tutor_agent():
    raw_json = '{"conversation": "Hello there!", "feedback": "Good job.", "target_corrections": []}'
    p1 = TutorAgent.parse_response(raw_json)
    assert p1["conversation"] == "Hello there!"

    raw_markdown = '```json\n{"conversation": "Keep going!", "feedback": null, "target_corrections": []}\n```'
    p2 = TutorAgent.parse_response(raw_markdown)
    assert p2["conversation"] == "Keep going!"

    raw_tags = "[CONVERSATION]\nGreat job!\n[FEEDBACK]\n- Minor issue."
    p3 = TutorAgent.parse_response(raw_tags)
    assert "Great job!" in p3["conversation"]

def test_downloader_validation():
    downloader = AudioDownloader()
    assert downloader.validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert downloader.validate_url("https://malicious-site.com/exploit.mp3") is False

def test_magic_bytes():
    assert validate_audio_magic_bytes(b"\x1a\x45\xdf\xa3") is True
    assert validate_audio_magic_bytes(b"RIFF\x24\x00\x00\x00WAVE") is True
    assert validate_audio_magic_bytes(b"ID3\x04\x00\x00") is True
    assert validate_audio_magic_bytes(b"MZ\x90\x00") is False

if __name__ == "__main__":
    test_scorer()
    test_tutor_agent()
    test_downloader_validation()
    test_magic_bytes()
    print("✅ All Python AI tests passed.")
