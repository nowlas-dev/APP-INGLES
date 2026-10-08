"""
LingoBeats — backend-ai/app/services/tutor_agent.py
Blindaje de parseo JSON, estructuración de respuestas pedagógicas del LLM
y catálogo de saludos de bienvenida contextuales con personalidad.
"""

from __future__ import annotations

import json
import random
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
#  Catálogo de Bienvenida Dinámico por Actitud/Estilo
# ─────────────────────────────────────────────────────────────

WELCOME_TEMPLATES: Dict[str, List[str]] = {
    "friendly": [
        "¡Hola! Qué gran elección practicar con '{song_title}' de {artist}. Vamos a disfrutar cada estrofa y afinar tu pronunciación paso a paso.",
        "¡Bienvenido a LingoBeats! Hoy cantaremos '{song_title}' de {artist}. Relájate, escucha el ritmo y diviértete aprendiendo inglés.",
        "¡Qué alegría tenerte aquí! '{song_title}' de {artist} es fantástica para mejorar tu fluidez y vocabulario. ¡Comencemos con toda la energía!",
    ],
    "funny": [
        "¡Vaya, vaya! Prepárate para cantar '{song_title}' de {artist} como en la ducha, pero aquí tu tutor IA te escucha atentamente. ¡A darlo todo!",
        "¡Atención! Prohibido desafinar en '{song_title}' de {artist}... Bueno, un poquito sí, pero los fonemas en inglés me los pronuncias perfecto, ¿trato?",
        "¡Llegó el momento estelar! Con '{song_title}' de {artist} vas a sonar mejor que el mismísimo artista original. ¡A cantar sin miedo!",
    ],
    "strict": [
        "Iniciando sesión de entrenamiento con '{song_title}' de {artist}. Exijo máxima atención a las consonantes y el ritmo. Concentración total.",
        "Objetivo fijado: dominar la dicción en '{song_title}' de {artist}. Cada error fonético será corregido. Pronuncia con claridad desde el primer verso.",
        "Sesión de disciplina fonética con '{song_title}' de {artist}. Cero murmullos: modula bien cada palabra y mantén la precisión vocal.",
    ],
}


def get_welcome_greeting(song_title: str, artist: str = "", attitude: str = "funny") -> str:
    """
    Elige una plantilla aleatoria para el estilo especificado y devuelve el saludo personalizado.
    Estilos disponibles: friendly, funny, strict (fallback: funny).
    """
    att = (attitude or "funny").lower().strip()
    if att not in WELCOME_TEMPLATES:
        att = "funny"

    title = (song_title or "esta canción").strip()
    art = (artist or "").strip()
    artist_display = art if art else "tu artista favorito"

    templates = WELCOME_TEMPLATES[att]
    template = random.choice(templates)
    return template.format(song_title=title, artist=artist_display)


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
        """Parser defensivo multi-etapa para respuestas JSON del LLM."""
        if not raw_text or not raw_text.strip():
            return {
                "conversation": "I couldn't hear that clearly. Could you try again?",
                "feedback": None,
                "target_corrections": [],
                "comprehension_question": "What would you like to practice?",
            }

        cleaned = raw_text.strip()
        if "```" in cleaned:
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

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

        return {
            "conversation": cleaned,
            "feedback": None,
            "target_corrections": [],
            "comprehension_question": None,
        }


__all__ = ["TutorAgent", "TutorOutputSchema", "WELCOME_TEMPLATES", "get_welcome_greeting"]
