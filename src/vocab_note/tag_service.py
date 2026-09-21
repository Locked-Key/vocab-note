"""3단계: 태그(다대다) + 단어장 검색·필터·정렬.

- 관계: word --< word_tag >-- tag (다대다, word 삭제 시 CASCADE)
- 태그명: 앞뒤 공백 정리·내부 공백 1칸으로 (표시용 원본 유지),
  중복 판단은 대소문자 무시 (`COLLATE NOCASE`)
"""

from __future__ import annotations

import re
import sqlite3

from .models import Sense, Tag, Word
from .vocab_service import VocabError, get_word


class TagError(VocabError):
    pass


def normalize_tag_name(name: str) -> str:
    """태그명 정리: strip + 내부 공백 1칸 (대소문자는 표시용으로 유지)."""
    return re.sub(r"\s+", " ", name.strip())


def get_or_create_tag(conn: sqlite3.Connection, name: str) -> Tag:
    """태그 조회 후 없으면 생성. 대소문자 무시하고 중복 판단."""
    cleaned = normalize_tag_name(name)
    if not cleaned:
        raise TagError("태그명은 비어 있을 수 없습니다.")
    row = conn.execute(
        "SELECT * FROM tag WHERE name = ? COLLATE NOCASE", (cleaned,)
    ).fetchone()
    if row is not None:
        return Tag(id=row["id"], name=row["name"])
    try:
        cur = conn.execute("INSERT INTO tag (name) VALUES (?)", (cleaned,))
        conn.commit()
    except sqlite3.IntegrityError:  # 동시 생성 등 정확한 중복 시 기존 행 반환
        row = conn.execute(
            "SELECT * FROM tag WHERE name = ? COLLATE NOCASE", (cleaned,)
        ).fetchone()
        if row is None:
            raise
        return Tag(id=row["id"], name=row["name"])
    return Tag(id=cur.lastrowid, name=cleaned)


def list_tags(conn: sqlite3.Connection) -> list[tuple[Tag, int]]:
    """(태그, 단어 수) 목록. 단어 수 내림차순 → 이름순."""
    rows = conn.execute(
        """SELECT t.id, t.name, COUNT(wt.word_id) AS word_count
           FROM tag t LEFT JOIN word_tag wt ON wt.tag_id = t.id
           GROUP BY t.id ORDER BY word_count DESC, t.name"""
    ).fetchall()
    return [(Tag(id=r["id"], name=r["name"]), r["word_count"]) for r in rows]


def get_word_tags(conn: sqlite3.Connection, word_id: int) -> list[Tag]:
    get_word(conn, word_id)  # 존재 확인
    rows = conn.execute(
        """SELECT t.id, t.name FROM tag t
           JOIN word_tag wt ON wt.tag_id = t.id
           WHERE wt.word_id = ? ORDER BY t.name""",
        (word_id,),
    ).fetchall()
    return [Tag(id=r["id"], name=r["name"]) for r in rows]


def tag_word(conn: sqlite3.Connection, word_id: int, name: str) -> Tag:
    """단어에 태그 붙이기 (이미 있으면 그대로)."""
    get_word(conn, word_id)  # 존재 확인
    tag = get_or_create_tag(conn, name)
    conn.execute(
        "INSERT OR IGNORE INTO word_tag (word_id, tag_id) VALUES (?, ?)",
        (word_id, tag.id),
    )
    conn.commit()
    return tag


def untag_word(conn: sqlite3.Connection, word_id: int, name: str) -> None:
    """단어에서 태그 떼기. 남은 단어가 없어도 태그 자체는 유지."""
    cleaned = normalize_tag_name(name)
    cur = conn.execute(
        """DELETE FROM word_tag WHERE word_id = ?
           AND tag_id IN (SELECT id FROM tag WHERE name = ? COLLATE NOCASE)""",
        (word_id, cleaned),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise TagError(f"태그 없음: word_id={word_id}, tag={cleaned}")


def _word_with_details(conn: sqlite3.Connection, word_row: sqlite3.Row) -> Word:
    sense_rows = conn.execute(
        "SELECT * FROM sense WHERE word_id = ? ORDER BY id", (word_row["id"],)
    ).fetchall()
    tag_rows = conn.execute(
        """SELECT t.id, t.name FROM tag t
           JOIN word_tag wt ON wt.tag_id = t.id
           WHERE wt.word_id = ? ORDER BY t.name""",
        (word_row["id"],),
    ).fetchall()
    return Word(
        id=word_row["id"],
        spelling=word_row["spelling"],
        normalized_spelling=word_row["normalized_spelling"],
        created_at=word_row["created_at"] or "",
        senses=[
            Sense(
                id=r["id"],
                word_id=r["word_id"],
                part_of_speech=r["part_of_speech"] or "",
                meaning_ko=r["meaning_ko"] or "",
                example_en=r["example_en"] or "",
                example_ko=r["example_ko"] or "",
            )
            for r in sense_rows
        ],
        tags=[Tag(id=r["id"], name=r["name"]) for r in tag_rows],
    )


def search_words(
    conn: sqlite3.Connection,
    query: str = "",
    tag: str = "",
    order: str = "alpha",
) -> list[Word]:
    """단어장 목록: 검색어(철자·뜻) + 태그 필터 + 정렬.

    - query: spelling/normalized_spelling/meaning_ko 부분 일치
    - tag: 해당 태그가 붙은 단어만 (대소문자 무시)
    - order: "alpha"(가나다/ABC순) | "recent"(최근 등록순)
    """
    if order not in ("alpha", "recent"):
        raise TagError("order는 alpha 또는 recent이어야 합니다.")
    q = query.strip()
    t = normalize_tag_name(tag) if tag.strip() else ""

    sql = "SELECT DISTINCT w.* FROM word w"
    joins: list[str] = []
    wheres: list[str] = []
    params: list[str] = []
    if t:
        joins.append(
            "JOIN word_tag wt ON wt.word_id = w.id "
            "JOIN tag tg ON tg.id = wt.tag_id"
        )
        wheres.append("tg.name = ? COLLATE NOCASE")
        params.append(t)
    if q:
        like = f"%{q}%"
        wheres.append(
            "(w.spelling LIKE ? OR w.normalized_spelling LIKE ? "
            "OR EXISTS (SELECT 1 FROM sense s WHERE s.word_id = w.id "
            "AND s.meaning_ko LIKE ?))"
        )
        params.extend([like, like.lower(), like])
    if joins:
        sql += " " + " ".join(joins)
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY w.id DESC" if order == "recent" else " ORDER BY w.normalized_spelling"

    rows = conn.execute(sql, params).fetchall()
    return [_word_with_details(conn, r) for r in rows]
