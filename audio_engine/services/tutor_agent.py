"""
LingoBeats — audio_engine/services/tutor_agent.py
Blindaje de parseo JSON y estructuración de respuestas pedagógicas del LLM.
"""

from __future__ import annotations

import json
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TutorOutputSchema(BaseModel):
    conversation: str = Field(description="Respuesta natural conversacional del tutor en inglés.")
    feedback: Optional[str] = Field(default=None, description="Explicación concisa de correcciones fonéticas o gramaticales.")
    target_corrections: List[str] = Field(default_factory=list, description="Lista de palabras o estructuras corregidas.")
    comprehension_question: Optional[str] = Field(default=None, description="Pregunta interactiva para sostener el turno.")


class TutorAgent:
    """Agente de tutoría con salida JSON estructurada y parser defensivo multi-etapa."""

    SYSTEM_INSTRUCTION = """You are "LingoBeats", an adaptive AI vocal and language coach.
You MUST output valid, raw JSON matching this schema exactly:
{
  "conversation": "Your conversational reply in target language (1-2 sentences).",
  "feedback": "Concise correction bullet points if mistakes occurred, or null if none.",
  "target_corrections": ["word1", "phrase2"],
  "comprehension_question": "An open question to test user comprehension."
}
Do NOT include markdown formatting (such as ```json), preambles, or postscripts. Output pure JSON only."""

    @staticmethod
    def parse_response(raw_text: str) -> Dict[str, Any]:
        """
        Parser defensivo:
        1. Intenta json.loads directo.
        2. Si falla, busca el bloque delimitado por '{' y '}'.
        3. Si contiene etiquetas legacy [CONVERSATION] y [FEEDBACK], las extrae.
        4. Si todo falla, construye un esquema predeterminado seguro sin romper el flujo.
        """
        if not raw_text or not raw_text.strip():
            return {
                "conversation": "I couldn't hear that clearly. Could you try again?",
                "feedback": None,
                "target_corrections": [],
                "comprehension_question": "What would you like to practice?",
            }

        cleaned = raw_text.strip()

        # Limpiar posibles bloques markdown ```json ... ```
        if "```" in cleaned:
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

        # Intento 1: JSON directo
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return {
                    "conversation": str(data.get("conversation", "")).strip(),
                    "feedback": data.get("feedback") if data.get("feedback") not in (None, "None", "none", "null") else None,
                    "target_corrections": list(data.get("target_corrections", [])),
                    "comprehension_question": data.get("comprehension_question"),
                }
        except Exception:
            pass

        # Intento 2: Aislar con Regex el primer bloque JSON balanceado
        json_match = re.search(r"(\{[\s\S]*\})", cleaned)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    return {
                        "conversation": str(data.get("conversation", "")).strip(),
                        "feedback": data.get("feedback") if data.get("feedback") not in (None, "None", "none", "null") else None,
                        "target_corrections": list(data.get("target_corrections", [])),
                        "comprehension_question": data.get("comprehension_question"),
                    }
            except Exception:
                pass

        # Intento 3: Formato tag legacy [CONVERSATION] / [FEEDBACK]
        conv_m = re.search(r"\[CONVERSATION\]\s*([\s\S]*?)(?=\[FEEDBACK\]|$)", cleaned, re.IGNORECASE)
        feed_m = re.search(r"\[FEEDBACK\]\s*([\s\S]*)", cleaned, re.IGNORECASE)
        if conv_m:
            conv_text = conv_m.group(1).strip()
            feed_text = feed_m.group(1).strip() if feed_m else None
            if feed_text and feed_text.lower() in {"none", "none.", "n/a", "no mistakes detected."}:
                feed_text = None
            return {
                "conversation": conv_text,
                "feedback": feed_text,
                "target_corrections": [],
                "comprehension_question": None,
            }

        # Intento 4: Fallback determinista seguro
        return {
            "conversation": cleaned,
            "feedback": None,
            "target_corrections": [],
            "comprehension_question": None,
        }
