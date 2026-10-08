"""
LingoBeats — audio_engine/services/scorer.py
Motor de puntuación fonética y léxica: normalización, WER, distancia Levenshtein y detección de fonemas omitidos.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Tuple


class PhoneticScorer:
    """Evaluador de precisión fonética y fonológica para karaoke y práctica de pronunciación."""

    CONTRACTIONS = {
        r"\bi'm\b": "i am",
        r"\byou're\b": "you are",
        r"\bhe's\b": "he is",
        r"\bshe's\b": "she is",
        r"\bit's\b": "it is",
        r"\bwe're\b": "we are",
        r"\bthey're\b": "they are",
        r"\bcan't\b": "cannot",
        r"\bdon't\b": "do not",
        r"\bdoesn't\b": "does not",
        r"\bdidn't\b": "did not",
        r"\bwon't\b": "will not",
        r"\bwouldn't\b": "would not",
        r"\bshouldn't\b": "should not",
        r"\bcouldn't\b": "could not",
        r"\bisn't\b": "is not",
        r"\baren't\b": "are not",
        r"\bwasn't\b": "was not",
        r"\bweren't\b": "were not",
        r"\bhaven't\b": "have not",
        r"\bhasn't\b": "has not",
        r"\bhadn't\b": "had not",
        r"\blet's\b": "let us",
        r"\bwhat's\b": "what is",
        r"\bthat's\b": "that is",
        r"\bthere's\b": "there is",
        r"\bwanna\b": "want to",
        r"\bgonna\b": "going to",
        r"\bgotta\b": "got to",
    }

    # Consonantes ocluidas y fricativas finales comúnmente omitidas por hispanohablantes
    FINAL_CONSONANTS = ("d", "t", "k", "p", "g", "b", "s", "z", "th", "nd", "nt", "st", "ld", "rk", "rt")

    def __init__(self, passing_threshold: float = 70.0):
        self.passing_threshold = passing_threshold

    def normalize(self, text: str) -> str:
        """
        Normaliza una cadena:
        - Minúsculas
        - Expansión sistemática de contracciones
        - Eliminación de signos de puntuación excepto apóstrofes internos
        - Colapso de espacios múltiples
        """
        if not text:
            return ""

        t = text.lower()
        for pattern, replacement in self.CONTRACTIONS.items():
            t = re.sub(pattern, replacement, t)

        # Elimina puntuación innecesaria conservando letras, dígitos y espacios
        t = re.sub(r"[^a-z0-9\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calcula la distancia Levenshtein estándar a nivel de caracteres con DP optimizado en espacio."""
        if len(s1) < len(s2):
            return PhoneticScorer.levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def compute_wer(self, reference: str, hypothesis: str) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calcula Word Error Rate (WER) entre referencia e hipótesis mediante programación dinámica.
        Retorna (wer_float, alignments).
        """
        ref_words = reference.split()
        hyp_words = hypothesis.split()

        r_len = len(ref_words)
        h_len = len(hyp_words)

        if r_len == 0:
            return (0.0 if h_len == 0 else 1.0, [])

        dp = [[0] * (h_len + 1) for _ in range(r_len + 1)]
        ops = [[None] * (h_len + 1) for _ in range(r_len + 1)]

        for i in range(r_len + 1):
            dp[i][0] = i
            ops[i][0] = "deletion"
        for j in range(h_len + 1):
            dp[0][j] = j
            ops[0][j] = "insertion"
        ops[0][0] = "match"

        for i in range(1, r_len + 1):
            for j in range(1, h_len + 1):
                if ref_words[i - 1] == hyp_words[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                    ops[i][j] = "match"
                else:
                    sub = dp[i - 1][j - 1] + 1
                    ins = dp[i][j - 1] + 1
                    delete = dp[i - 1][j] + 1

                    min_val = min(sub, ins, delete)
                    dp[i][j] = min_val
                    if min_val == sub:
                        ops[i][j] = "substitution"
                    elif min_val == delete:
                        ops[i][j] = "deletion"
                    else:
                        ops[i][j] = "insertion"

        wer = dp[r_len][h_len] / float(r_len)

        # Reconstrucción de alineamiento
        alignments = []
        i, j = r_len, h_len
        while i > 0 or j > 0:
            op = ops[i][j]
            if op == "match":
                alignments.append({"op": "match", "ref": ref_words[i - 1], "hyp": hyp_words[j - 1]})
                i -= 1
                j -= 1
            elif op == "substitution":
                alignments.append({"op": "substitution", "ref": ref_words[i - 1], "hyp": hyp_words[j - 1]})
                i -= 1
                j -= 1
            elif op == "deletion":
                alignments.append({"op": "deletion", "ref": ref_words[i - 1], "hyp": None})
                i -= 1
            elif op == "insertion":
                alignments.append({"op": "insertion", "ref": None, "hyp": hyp_words[j - 1]})
                j -= 1
            else:
                break

        alignments.reverse()
        return wer, alignments

    def detect_phonetic_discrepancies(self, alignments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analiza las discrepancias para detectar patrones fonológicos específicos,
        como consonantes finales omitidas ('land' -> 'lan', 'dark' -> 'dar', 'went' -> 'wen').
        """
        discrepancies = []

        for item in alignments:
            op = item["op"]
            ref = item.get("ref")
            hyp = item.get("hyp")

            if op == "match":
                continue

            if op == "substitution" and ref and hyp:
                # Comprobación de omisión de consonante final
                detected_drop = None
                for ending in sorted(self.FINAL_CONSONANTS, key=len, reverse=True):
                    if ref.endswith(ending):
                        expected_stem = ref[: -len(ending)]
                        if hyp == expected_stem or (hyp.startswith(expected_stem) and len(hyp) < len(ref)):
                            detected_drop = ending
                            break

                char_dist = self.levenshtein_distance(ref, hyp)
                sim = 1.0 - (char_dist / max(len(ref), len(hyp), 1))

                if detected_drop:
                    discrepancies.append({
                        "type": "dropped_final_consonant",
                        "target_word": ref,
                        "pronounced_word": hyp,
                        "dropped_phoneme": detected_drop,
                        "similarity": round(sim, 3),
                        "explanation": f"Did not pronounce final sound '{detected_drop}' in '{ref}'. Pronounced as '{hyp}'."
                    })
                else:
                    discrepancies.append({
                        "type": "mispronunciation",
                        "target_word": ref,
                        "pronounced_word": hyp,
                        "similarity": round(sim, 3),
                        "char_distance": char_dist,
                        "explanation": f"Expected '{ref}' but received '{hyp}'."
                    })

            elif op == "deletion" and ref:
                discrepancies.append({
                    "type": "omitted_word",
                    "target_word": ref,
                    "pronounced_word": None,
                    "explanation": f"Word '{ref}' was omitted completely."
                })

            elif op == "insertion" and hyp:
                discrepancies.append({
                    "type": "inserted_word",
                    "target_word": None,
                    "pronounced_word": hyp,
                    "explanation": f"Extra word '{hyp}' was pronounced."
                })

        return discrepancies

    def score(self, target_text: str, transcript: str) -> Dict[str, Any]:
        """
        Ejecuta la evaluación integral y retorna métricas detalladas.

        Returns:
            Dict: wer, accuracy_score, passed, discrepancies, normalized_target, normalized_transcript
        """
        norm_target = self.normalize(target_text)
        norm_hyp = self.normalize(transcript)

        wer, alignments = self.compute_wer(norm_target, norm_hyp)
        discrepancies = self.detect_phonetic_discrepancies(alignments)

        # Precisión porcentual ponderada: 100 - (WER * 100), acotada en [0, 100]
        accuracy = max(0.0, min(100.0, (1.0 - wer) * 100.0))
        passed = accuracy >= self.passing_threshold

        return {
            "wer": round(wer, 4),
            "accuracy_score": round(accuracy, 2),
            "passed": passed,
            "passing_threshold": self.passing_threshold,
            "discrepancies": discrepancies,
            "normalized_target": norm_target,
            "normalized_transcript": norm_hyp,
            "total_words_target": len(norm_target.split()),
            "total_words_pronounced": len(norm_hyp.split()),
        }
