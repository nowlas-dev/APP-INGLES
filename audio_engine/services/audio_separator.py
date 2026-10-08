"""
LingoBeats — audio_engine/services/audio_separator.py
Separador de pistas de audio (stems) usando Demucs (htdemucs) con soporte defensivo GPU/CPU.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Dict, Any


class StemSeparator:
    """Separador de pistas vocales e instrumentales utilizando el modelo htdemucs de Demucs."""

    def __init__(self, model_name: str = "htdemucs"):
        self.model_name = model_name
        self.device = self._detect_device()

    def _detect_device(self) -> str:
        """Determina si CUDA está disponible para aceleración GPU o conmuta a CPU."""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def separate_vocals(self, audio_path: str, output_dir: str) -> Dict[str, str]:
        """
        Separa la voz de la pista instrumental a partir de un archivo de audio.

        Args:
            audio_path: Ruta al archivo de audio origen (WAV, MP3, FLAC).
            output_dir: Directorio donde se guardarán los stems generados.

        Returns:
            Dict con las rutas absolutas: {"vocals_path": str, "instrumental_path": str}

        Raises:
            FileNotFoundError: Si audio_path no existe.
            RuntimeError: Si la ejecución de Demucs falla.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Archivo de audio no encontrado: {audio_path}")

        os.makedirs(output_dir, exist_ok=True)
        abs_audio_path = os.path.abspath(audio_path)
        track_stem_name = os.path.splitext(os.path.basename(abs_audio_path))[0]

        # Comando CLI estándar de Demucs para 2 stems (vocals / no_vocals)
        # demucs --two-stems=vocals -n htdemucs -d <device> -o <output_dir> <audio_path>
        cmd = [
            sys.executable,
            "-m",
            "demucs.separate",
            "--two-stems=vocals",
            "-n",
            self.model_name,
            "-d",
            self.device,
            "-o",
            os.path.abspath(output_dir),
            abs_audio_path,
        ]

        print(f"[DEMUCS] 🎵 Iniciando separación de stems con modelo '{self.model_name}' en dispositivo '{self.device}'...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,  # 5 minutos máximo
            )
            if result.returncode != 0:
                # Si falló en CUDA, reintentar una vez en CPU
                if self.device == "cuda":
                    print("[DEMUCS] ⚠️ Falló ejecución en GPU. Reintentando en CPU...")
                    cmd[cmd.index("-d") + 1] = "cpu"
                    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600)

                if result.returncode != 0:
                    raise RuntimeError(f"Demucs falló (code {result.returncode}): {result.stderr or result.stdout}")

        except FileNotFoundError:
            raise RuntimeError("Demucs no está instalado en el entorno Python. Instálelo con: pip install demucs")
        except subprocess.TimeoutExpired:
            raise TimeoutError("La separación de pistas excedió el tiempo límite de espera.")

        # Demucs crea: output_dir/htdemucs/{track_stem_name}/vocals.wav y no_vocals.wav
        demucs_track_dir = os.path.join(output_dir, self.model_name, track_stem_name)
        vocals_file = os.path.join(demucs_track_dir, "vocals.wav")
        instrumental_file = os.path.join(demucs_track_dir, "no_vocals.wav")

        if not os.path.exists(vocals_file) or not os.path.exists(instrumental_file):
            # Búsqueda por si demucs exportó con otra extensión o nombre
            found_vocals = None
            found_inst = None
            if os.path.exists(demucs_track_dir):
                for f in os.listdir(demucs_track_dir):
                    lower = f.lower()
                    if "vocals" in lower and "no" not in lower:
                        found_vocals = os.path.join(demucs_track_dir, f)
                    elif "no_vocals" in lower or "instrumental" in lower:
                        found_inst = os.path.join(demucs_track_dir, f)
            if not found_vocals or not found_inst:
                raise FileNotFoundError(f"No se localizaron los archivos separados en: {demucs_track_dir}")
            vocals_file = found_vocals
            instrumental_file = found_inst

        # Crear copias directas o devolver rutas absolutas estructuradas
        final_vocals = os.path.join(output_dir, f"{track_stem_name}_vocals.wav")
        final_inst = os.path.join(output_dir, f"{track_stem_name}_instrumental.wav")

        shutil.copy2(vocals_file, final_vocals)
        shutil.copy2(instrumental_file, final_inst)

        print(f"[DEMUCS] ✅ Stems generados exitosamente:\n  Voz: {final_vocals}\n  Instrumental: {final_inst}")

        return {
            "vocals_path": os.path.abspath(final_vocals),
            "instrumental_path": os.path.abspath(final_inst),
        }
