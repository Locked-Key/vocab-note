"""1단계: 단어장 핵심 CRUD. UI와 분리된 순수 데이터 로직입니다."""

from __future__ import annotations

import re
import sqlite3

from .models import Sense, Word


class VocabError(Exception):
    """단어장 도메인 예외의 베이스."""


class DuplicateWordError(VocabError):
    """같은 normalized_spelling이 이미 있을 때."""


class WordNotFoundError(VocabError):
    pass


class SenseNotFoundError(VocabError):
    pass


def normalize_spelling(spelling: str) -> str:
    """철자 정규화: 앞뒤 공백 제거 + 소문자 + 내부 공백 1칸으로.

    예: "  Apple  " -> "apple" (2단계 중복 검사의 기준이 됨)
    """
    return re.sub(r"\s+", " ", spelling.strip().lower())


def _row_to_sense(row: sqlite3.Row) -> Sense:
    return Sense(
        id=row["id"],
        word_id=row["word_id"],
        part_of_speech=row["part_of_speech"] or "",
        meaning_ko=row["meaning_ko"] or "",
        example_en=row["example_en"] or "",
        example_ko=row["example_ko"] or "",
    )


def _senses_of(conn: sqlite3.Connection, word_id: int) -> list[Sense]:
    rows = conn.execute(
        "SELECT * FROM sense WHERE word_id = ? ORDER BY id", (word_id,)
    ).fetchall()
    return [_row_to_sense(r) for r in rows]


def add_word(conn: sqlite3.Connection, spelling: str) -> Word:
    """단어(철자)만 먼저 등록. 뜻은 add_sense로 따로 붙입니다."""
    if not spelling or not spelling.strip():
        raise VocabError("spelling은 비어 있을 수 없습니다.")
    normalized = normalize_spelling(spelling)
    try:
        cur = conn.execute(
            "INSERT INTO word (spelling, normalized_spelling) VALUES (?, ?)",
            (spelling.strip(), normalized),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise DuplicateWordError(f"이미 등록된 단어입니다: {spelling.strip()}") from e
    return get_word(conn, cur.lastrowid)


def get_word(conn: sqlite3.Connection, word_id: int) -> Word:
    row = conn.execute("SELECT * FROM word WHERE id = ?", (word_id,)).fetchone()
    if row is None:
        raise WordNotFoundError(f"word id={word_id} 없음")
    return Word(
        id=row["id"],
        spelling=row["spelling"],
        normalized_spelling=row["normalized_spelling"],
        created_at=row["created_at"] or "",
        senses=_senses_of(conn, row["id"]),
    )


def get_word_by_spelling(conn: sqlite3.Connection, spelling: str) -> Word | None:
    row = conn.execute(
        "SELECT * FROM word WHERE normalized_spelling = ?",
        (normalize_spelling(spelling),),
    ).fetchone()
    if row is None:
        return None
    return get_word(conn, row["id"])


def find_duplicate(conn: sqlite3.Connection, spelling: str) -> Word | None:
    """2단계: 철자 기준 중복 조회.

    `normalized_spelling`(소문자·공백 정리)에 UNIQUE가 걸려 있어
    "Apple" / " apple " / "APPLE"은 모두 같은 단어로 취급됩니다.
    중복이면 기존 Word(뜻 포함), 없으면 None.
    """
    if not spelling or not spelling.strip():
        return None
    return get_word_by_spelling(conn, spelling)


def list_words(conn: sqlite3.Connection) -> list[Word]:
    rows = conn.execute("SELECT * FROM word ORDER BY normalized_spelling").fetchall()
    return [
        Word(
            id=r["id"],
            spelling=r["spelling"],
            normalized_spelling=r["normalized_spelling"],
            created_at=r["created_at"] or "",
            senses=_senses_of(conn, r["id"]),
        )
        for r in rows
    ]


def add_sense(
    conn: sqlite3.Connection,
    word_id: int,
    part_of_speech: str = "",
    meaning_ko: str = "",
    example_en: str = "",
    example_ko: str = "",
) -> Sense:
    """한 단어에 뜻을 하나 추가 (동음이의어 = sense 여러 개)."""
    if not meaning_ko or not meaning_ko.strip():
        raise VocabError("meaning_ko(뜻)는 비어 있을 수 없습니다.")
    # word 존재 확인 (없으면 WordNotFoundError)
    get_word(conn, word_id)
    cur = conn.execute(
        """INSERT INTO sense (word_id, part_of_speech, meaning_ko, example_en, example_ko)
           VALUES (?, ?, ?, ?, ?)""",
        (
            word_id,
            part_of_speech.strip(),
            meaning_ko.strip(),
            example_en.strip(),
            example_ko.strip(),
        ),
    )
    conn.commit()
    return get_sense(conn, cur.lastrowid)


def get_sense(conn: sqlite3.Connection, sense_id: int) -> Sense:
    row = conn.execute("SELECT * FROM sense WHERE id = ?", (sense_id,)).fetchone()
    if row is None:
        raise SenseNotFoundError(f"sense id={sense_id} 없음")
    return _row_to_sense(row)


def update_sense(
    conn: sqlite3.Connection,
    sense_id: int,
    *,
    part_of_speech: str | None = None,
    meaning_ko: str | None = None,
    example_en: str | None = None,
    example_ko: str | None = None,
) -> Sense:
    sense = get_sense(conn, sense_id)  # 존재 확인
    fields: dict[str, str] = {}
    if part_of_speech is not None:
        fields["part_of_speech"] = part_of_speech.strip()
    if meaning_ko is not None:
        if not meaning_ko.strip():
            raise VocabError("meaning_ko(뜻)는 비어 있을 수 없습니다.")
        fields["meaning_ko"] = meaning_ko.strip()
    if example_en is not None:
        fields["example_en"] = example_en.strip()
    if example_ko is not None:
        fields["example_ko"] = example_ko.strip()
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE sense SET {sets} WHERE id = ?", (*fields.values(), sense.id)
        )
        conn.commit()
    return get_sense(conn, sense_id)


def delete_sense(conn: sqlite3.Connection, sense_id: int) -> None:
    cur = conn.execute("DELETE FROM sense WHERE id = ?", (sense_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise SenseNotFoundError(f"sense id={sense_id} 없음")


def delete_word(conn: sqlite3.Connection, word_id: int) -> None:
    """단어 삭제 시 sense/word_tag/quiz 기록도 CASCADE로 함께 삭제됩니다."""
    cur = conn.execute("DELETE FROM word WHERE id = ?", (word_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise WordNotFoundError(f"word id={word_id} 없음")


def update_word_spelling(conn: sqlite3.Connection, word_id: int, new_spelling: str) -> Word:
    if not new_spelling or not new_spelling.strip():
        raise VocabError("spelling은 비어 있을 수 없습니다.")
    get_word(conn, word_id)  # 존재 확인
    try:
        conn.execute(
            "UPDATE word SET spelling = ?, normalized_spelling = ? WHERE id = ?",
            (new_spelling.strip(), normalize_spelling(new_spelling), word_id),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise DuplicateWordError(
            f"이미 등록된 단어입니다: {new_spelling.strip()}"
        ) from e
    return get_word(conn, word_id)
