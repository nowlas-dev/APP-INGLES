-- =============================================================
--  LingoVibe v2 — SQLite Schema
--  Auto-aplicado por database.py en el primer arranque.
-- =============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- -------------------------------------------------------------
--  1. Usuarios
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key    TEXT UNIQUE NOT NULL DEFAULT 'usr_001',
    target_lang TEXT NOT NULL DEFAULT 'en-US',
    cefr_level  TEXT NOT NULL DEFAULT 'B2'
                CHECK(cefr_level IN ('A1','A2','B1','B2','C1','C2')),
    persona     TEXT NOT NULL DEFAULT 'friendly_peer',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Trigger: actualiza updated_at automáticamente
CREATE TRIGGER IF NOT EXISTS users_updated_at
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Usuario por defecto (migración desde memory_profile.json)
INSERT OR IGNORE INTO users (user_key, target_lang, cefr_level, persona)
VALUES ('usr_001', 'en-US', 'B2', 'friendly_peer');

-- -------------------------------------------------------------
--  2. Sesiones de práctica
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cefr_level  TEXT NOT NULL,
    started_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at    DATETIME,
    turns_count INTEGER DEFAULT 0,
    score       REAL CHECK(score IS NULL OR (score >= 0 AND score <= 10))
);

-- -------------------------------------------------------------
--  3. Turnos individuales (cada intercambio usuario ↔ tutor)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS turns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL,
    input_type      TEXT NOT NULL CHECK(input_type IN ('text', 'audio')),
    user_input_text TEXT,
    audio_path      TEXT,
    transcript      TEXT,
    tutor_conv      TEXT,
    tutor_feedback  TEXT,
    llm_provider    TEXT,
    latency_ms      INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, seq)
);

-- -------------------------------------------------------------
--  4. Debilidades persistentes por usuario
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weaknesses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    frequency   INTEGER DEFAULT 1,
    last_seen   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, description)
);

-- Trigger: incrementa frecuencia en lugar de duplicar
CREATE TRIGGER IF NOT EXISTS weaknesses_upsert_freq
AFTER INSERT ON weaknesses
WHEN (SELECT COUNT(*) FROM weaknesses
      WHERE user_id = NEW.user_id AND description = NEW.description) > 1
BEGIN
    UPDATE weaknesses
    SET frequency  = frequency + 1,
        last_seen  = CURRENT_TIMESTAMP
    WHERE user_id     = NEW.user_id
      AND description = NEW.description
      AND id         != NEW.id;
    DELETE FROM weaknesses WHERE id = NEW.id;
END;

-- Debilidades por defecto (migración desde memory_profile.json)
INSERT OR IGNORE INTO weaknesses (user_id, description)
SELECT u.id, 'Subject-verb agreement (3rd person singular)' FROM users u WHERE u.user_key = 'usr_001'
UNION ALL
SELECT u.id, 'Second conditional (if + past simple vs would)' FROM users u WHERE u.user_key = 'usr_001'
UNION ALL
SELECT u.id, 'Preposition collocations (depend on, think about/of)' FROM users u WHERE u.user_key = 'usr_001';

-- -------------------------------------------------------------
--  5. Banco de vocabulario
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vocabulary (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    word       TEXT NOT NULL,
    mastery    REAL DEFAULT 0.0 CHECK(mastery >= 0.0 AND mastery <= 1.0),
    added_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, word)
);

-- Vocabulario inicial (migración)
INSERT OR IGNORE INTO vocabulary (user_id, word, mastery)
SELECT u.id, 'tone down', 0.8 FROM users u WHERE u.user_key = 'usr_001'
UNION ALL
SELECT u.id, 'buffer', 0.9 FROM users u WHERE u.user_key = 'usr_001';


-- -------------------------------------------------------------
--  6. Estadísticas agregadas por usuario (vista)
-- -------------------------------------------------------------
CREATE VIEW IF NOT EXISTS user_stats AS
SELECT
    u.id            AS user_id,
    u.user_key,
    u.cefr_level,
    COUNT(DISTINCT s.id)         AS sessions_completed,
    COALESCE(SUM(s.turns_count), 0) AS total_turns,
    COALESCE(AVG(s.score), 0)    AS avg_score
FROM users u
LEFT JOIN sessions s ON s.user_id = u.id
GROUP BY u.id;

-- -------------------------------------------------------------
--  7. Caché de letras musicales (LRCLIB)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lyrics_cache (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    query_key    TEXT UNIQUE NOT NULL,
    track_name   TEXT NOT NULL,
    artist_name  TEXT,
    duration     REAL,
    raw_lrc      TEXT NOT NULL,
    stanzas_json TEXT NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

