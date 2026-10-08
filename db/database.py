"""
LingoVibe v2 — db/database.py
Módulo de acceso a datos SQLite (async con aiosqlite).
Importado por audio_engine y orchestrator (via HTTP API).
"""

from __future__ import annotations

import os
import aiosqlite
from typing import Any, Dict, List, Optional

# Rutas absolutas resueltas desde la ubicación de este archivo
_HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(_HERE, "schema.sql")
DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(_HERE, "lingvovibe.db")
)


# ─────────────────────────────────────────────────────────────
#  Inicialización y conexión
# ─────────────────────────────────────────────────────────────

class DatabaseConnectionContext:
    """
    Context manager resiliente para aiosqlite.
    Previene el error 'threads can only be started once' permitiendo
    tanto 'async with await get_db() as db:' como 'async with get_db() as db:'.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.db = None

    def __await__(self):
        return self._open().__await__()

    async def _open(self):
        if self.db is None:
            self.db = await aiosqlite.connect(self.db_path)
            self.db.row_factory = aiosqlite.Row
            await self.db.execute("PRAGMA journal_mode = WAL;")
            await self.db.execute("PRAGMA foreign_keys = ON;")
        return self

    async def __aenter__(self):
        if self.db is None:
            await self._open()
        return self.db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            await self.db.close()
            self.db = None

    def __getattr__(self, name):
        if self.db:
            return getattr(self.db, name)
        raise AttributeError(name)


def get_db() -> DatabaseConnectionContext:
    """Abre y configura la conexión SQLite de forma segura."""
    return DatabaseConnectionContext(DB_PATH)



async def init_db() -> None:
    """
    Aplica el schema.sql al arranque si las tablas no existen.
    Llamar una sola vez desde el startup event de FastAPI.
    """
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    async with await get_db() as db:
        await db.executescript(schema_sql)
        await db.commit()
    print(f"[DB] ✅ Schema aplicado correctamente → {DB_PATH}")


# ─────────────────────────────────────────────────────────────
#  Usuarios
# ─────────────────────────────────────────────────────────────

async def get_user(user_key: str = "usr_001") -> Optional[Dict[str, Any]]:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_key = ?", (user_key,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_user_level(user_key: str, cefr_level: str) -> bool:
    """Actualiza el nivel CEFR del usuario. Devuelve True si actualizó algo."""
    async with await get_db() as db:
        cursor = await db.execute(
            "UPDATE users SET cefr_level = ? WHERE user_key = ?",
            (cefr_level, user_key),
        )
        await db.commit()
        return cursor.rowcount > 0


# ─────────────────────────────────────────────────────────────
#  Sesiones
# ─────────────────────────────────────────────────────────────

async def create_session(user_id: int, cefr_level: str) -> int:
    """Crea una nueva sesión y devuelve su ID."""
    async with await get_db() as db:
        cursor = await db.execute(
            "INSERT INTO sessions (user_id, cefr_level) VALUES (?, ?)",
            (user_id, cefr_level),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def close_session(session_id: int, score: Optional[float] = None) -> None:
    """Marca la sesión como cerrada con timestamp y score opcional."""
    async with await get_db() as db:
        await db.execute(
            """
            UPDATE sessions
            SET ended_at = CURRENT_TIMESTAMP,
                score    = ?
            WHERE id = ?
            """,
            (score, session_id),
        )
        await db.commit()


async def increment_session_turns(session_id: int) -> None:
    async with await get_db() as db:
        await db.execute(
            "UPDATE sessions SET turns_count = turns_count + 1 WHERE id = ?",
            (session_id,),
        )
        await db.commit()


async def get_session(session_id: int) -> Optional[Dict[str, Any]]:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────
#  Turnos
# ─────────────────────────────────────────────────────────────

async def save_turn(
    session_id: int,
    seq: int,
    input_type: str,
    user_input_text: Optional[str] = None,
    audio_path: Optional[str] = None,
    transcript: Optional[str] = None,
    tutor_conv: Optional[str] = None,
    tutor_feedback: Optional[str] = None,
    llm_provider: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> int:
    """Inserta un turno completo. Devuelve el ID del turno."""
    async with await get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO turns
              (session_id, seq, input_type, user_input_text, audio_path,
               transcript, tutor_conv, tutor_feedback, llm_provider, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, seq, input_type, user_input_text, audio_path,
                transcript, tutor_conv, tutor_feedback, llm_provider, latency_ms,
            ),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_session_turns(session_id: int) -> List[Dict[str, Any]]:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY seq ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
#  Debilidades
# ─────────────────────────────────────────────────────────────

async def get_weaknesses(user_id: int) -> List[str]:
    """Devuelve las debilidades activas ordenadas por frecuencia descendente."""
    async with await get_db() as db:
        cursor = await db.execute(
            """
            SELECT description FROM weaknesses
            WHERE user_id = ?
            ORDER BY frequency DESC, last_seen DESC
            LIMIT 10
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [r["description"] for r in rows]


async def upsert_weakness(user_id: int, description: str) -> None:
    """Inserta o incrementa la frecuencia de una debilidad."""
    async with await get_db() as db:
        await db.execute(
            """
            INSERT INTO weaknesses (user_id, description, frequency, last_seen)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, description)
            DO UPDATE SET
                frequency = frequency + 1,
                last_seen = CURRENT_TIMESTAMP
            """,
            (user_id, description),
        )
        await db.commit()


# ─────────────────────────────────────────────────────────────
#  Vocabulario
# ─────────────────────────────────────────────────────────────

async def get_vocabulary(user_id: int) -> List[Dict[str, Any]]:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT word, mastery FROM vocabulary WHERE user_id = ? ORDER BY mastery DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def upsert_vocabulary(user_id: int, word: str, mastery: float) -> None:
    async with await get_db() as db:
        await db.execute(
            """
            INSERT INTO vocabulary (user_id, word, mastery)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, word)
            DO UPDATE SET mastery = excluded.mastery
            """,
            (user_id, word, mastery),
        )
        await db.commit()


# ─────────────────────────────────────────────────────────────
#  Perfil completo (para el endpoint GET /api/profile)
# ─────────────────────────────────────────────────────────────

async def get_full_profile(user_key: str = "usr_001") -> Dict[str, Any]:
    """
    Devuelve un dict con usuario + estadísticas + debilidades + vocabulario.
    Compatible con el formato de memory_profile.json de la v1.
    """
    async with await get_db() as db:
        # Datos del usuario y stats agregadas
        cursor = await db.execute(
            """
            SELECT u.*, s.sessions_completed, s.total_turns, s.avg_score
            FROM users u
            LEFT JOIN user_stats s ON s.user_id = u.id
            WHERE u.user_key = ?
            """,
            (user_key,),
        )
        user_row = await cursor.fetchone()
        if not user_row:
            return {}

        user = dict(user_row)
        user_id = user["id"]

        weaknesses = await get_weaknesses(user_id)
        vocab = await get_vocabulary(user_id)

        return {
            "user_id": user["user_key"],
            "target_language": user["target_lang"],
            "current_level": user["cefr_level"],
            "persona": user["persona"],
            "stats": {
                "sessions_completed": user.get("sessions_completed", 0),
                "total_turns": user.get("total_turns", 0),
                "avg_score": round(user.get("avg_score", 0.0), 2),
            },
            "persistent_weaknesses": weaknesses,
            "vocabulary_bank": vocab,
        }


# ─────────────────────────────────────────────────────────────
#  Caché de Letras (LRCLIB)
# ─────────────────────────────────────────────────────────────

async def get_lyrics_cache(query_key: str) -> Optional[Dict[str, Any]]:
    """Obtiene letras cacheadas por query_key ('track_name::artist_name')."""
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM lyrics_cache WHERE query_key = ?", (query_key,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def save_lyrics_cache(
    query_key: str,
    track_name: str,
    artist_name: Optional[str],
    duration: Optional[float],
    raw_lrc: str,
    stanzas_json: str,
) -> int:
    """Inserta o reemplaza letras en la tabla lyrics_cache."""
    async with await get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO lyrics_cache (query_key, track_name, artist_name, duration, raw_lrc, stanzas_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(query_key) DO UPDATE SET
                track_name = excluded.track_name,
                artist_name = excluded.artist_name,
                duration = excluded.duration,
                raw_lrc = excluded.raw_lrc,
                stanzas_json = excluded.stanzas_json,
                created_at = CURRENT_TIMESTAMP
            """,
            (query_key, track_name, artist_name, duration, raw_lrc, stanzas_json),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────
#  Rotación y Purga de Archivos de Audio
# ─────────────────────────────────────────────────────────────

def purge_old_audio_files(storage_dir: str, max_age_days: int = 7) -> int:
    """
    Elimina archivos de audio en storage_dir que tengan más de max_age_days días.
    Retorna el número de archivos purgados.
    """
    import time
    if not os.path.exists(storage_dir):
        return 0

    now = time.time()
    cutoff = now - (max_age_days * 86400)
    purged_count = 0

    for root, dirs, files in os.walk(storage_dir, topdown=False):
        for f in files:
            file_path = os.path.join(root, f)
            try:
                stat = os.stat(file_path)
                if stat.st_mtime < cutoff:
                    os.remove(file_path)
                    purged_count += 1
            except OSError:
                pass
        # Elimina subdirectorios vacíos
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
            except OSError:
                pass

    return purged_count

