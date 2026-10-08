"""
LingoBeats — audio_engine/services/downloader.py
Descargador automatizado de audio envolviendo yt-dlp con validación estricta de dominios y extracción optimizada.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from typing import Dict, Any, Optional

ALLOWED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "soundcloud.com",
    "www.soundcloud.com",
}


class AudioDownloader:
    """Descargador de audio seguro y optimizado con yt-dlp."""

    def __init__(self, sample_rate: int = 44100, audio_format: str = "mp3", timeout_seconds: int = 45):
        self.sample_rate = sample_rate
        self.audio_format = audio_format.lower()
        self.timeout_seconds = timeout_seconds

    def validate_url(self, url: str) -> bool:
        """Valida que la URL provenga exclusivamente de dominios autorizados para prevenir SSRF/inyección."""
        try:
            parsed = urllib.parse.urlparse(url.strip())
            if parsed.scheme not in ("http", "https"):
                return False
            hostname = parsed.hostname.lower() if parsed.hostname else ""
            return hostname in ALLOWED_DOMAINS or any(hostname.endswith("." + d) for d in ALLOWED_DOMAINS)
        except Exception:
            return False

    def download_audio(self, url: str, output_dir: str) -> Dict[str, Any]:
        """
        Descarga y extrae la pista de audio con re-muestreo configurado.

        Args:
            url: URL del recurso (YouTube, SoundCloud).
            output_dir: Directorio de destino.

        Returns:
            Dict con metadatos: title, artist, duration, audio_path, format, id.

        Raises:
            ValueError: Si la URL no es válida o permitida.
            RuntimeError: Si yt-dlp falla o la descarga excede el timeout.
        """
        if not self.validate_url(url):
            raise ValueError(f"URL no autorizada o inválida: '{url}'. Dominios permitidos: {', '.join(sorted(ALLOWED_DOMAINS))}")

        os.makedirs(output_dir, exist_ok=True)

        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("La librería 'yt-dlp' no está instalada. Ejecute: pip install yt-dlp")

        # Plantilla segura de archivo
        outtmpl = os.path.join(output_dir, "%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "socket_timeout": self.timeout_seconds,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": "192",
                }
            ],
            "postprocessor_args": [
                "-ar", str(self.sample_rate),
                "-ac", "2",
            ],
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise RuntimeError("yt-dlp no pudo extraer información del recurso.")

                video_id = info.get("id", "track")
                title = info.get("title", "Unknown Title")
                artist = info.get("artist") or info.get("uploader") or info.get("creator") or "Unknown Artist"
                duration = float(info.get("duration") or 0.0)

                expected_path = os.path.join(output_dir, f"{video_id}.{self.audio_format}")
                if not os.path.exists(expected_path):
                    # Búsqueda alternativa por si la extensión varió
                    candidates = [
                        os.path.join(output_dir, f)
                        for f in os.listdir(output_dir)
                        if f.startswith(video_id)
                    ]
                    if candidates:
                        expected_path = candidates[0]
                    else:
                        raise FileNotFoundError(f"Archivo de audio descargado no encontrado en {output_dir}")

                return {
                    "id": video_id,
                    "title": title,
                    "artist": artist,
                    "duration": duration,
                    "audio_path": os.path.abspath(expected_path),
                    "format": self.audio_format,
                    "sample_rate": self.sample_rate,
                }
        except Exception as exc:
            raise RuntimeError(f"Error durante la descarga con yt-dlp: {exc}")
