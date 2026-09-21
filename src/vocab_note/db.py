"""SQLite 연결 + 스키마 초기화.

1단계에서 Word/Sense CRUD가 이 모듈 위에 올라갑니다.
지금(0단계)은 테이블 생성과 연결 확인만 합니다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS word (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spelling TEXT NOT NULL,
    normalized_spelling TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sense (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL REFERENCES word(id) ON DELETE CASCADE,
    part_of_speech TEXT NOT NULL DEFAULT '',
    meaning_ko TEXT NOT NULL,
    example_en TEXT NOT NULL DEFAULT '',
    example_ko TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sense_word_id ON sense(word_id);

CREATE TABLE IF NOT EXISTS tag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS word_tag (
    word_id INTEGER NOT NULL REFERENCES word(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    PRIMARY KEY (word_id, tag_id)
);

CREATE TABLE IF NOT EXISTS quiz_attempt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_id INTEGER NOT NULL REFERENCES sense(id) ON DELETE CASCADE,
    direction TEXT NOT NULL,           -- en_to_ko / ko_to_en
    is_correct INTEGER NOT NULL,       -- 0 / 1
    answered_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_quiz_attempt_sense ON quiz_attempt(sense_id);
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """DB 연결을 반환합니다. data/ 폴더는 자동 생성됩니다."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str | None = None) -> Path:
    """스키마를 생성하고 DB 파일 경로를 반환합니다."""
    path = Path(db_path) if db_path else DB_PATH
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return path


def list_tables(db_path: Path | str | None = None) -> list[str]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()
