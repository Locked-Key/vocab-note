"""6단계: 학습 기록 집계. quiz_attempt 테이블을 읽어 통계만 만듭니다.

- 날짜: answered_at은 UTC "YYYY-MM-DD HH:MM:SS" 문자열 → substr로 일자 집계
- 모든 함수는 읽기 전용 (INSERT 없음)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class OverallStats:
    total: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class DirectionStats:
    direction: str
    total: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class DayStats:
    day: str  # "YYYY-MM-DD"
    total: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class SenseStats:
    sense_id: int
    spelling: str
    meaning_ko: str
    total: int
    correct: int
    last_answered_at: str

    @property
    def wrong(self) -> int:
        return self.total - self.correct

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class AttemptRecord:
    id: int
    spelling: str
    meaning_ko: str
    direction: str
    is_correct: bool
    answered_at: str


def overall_stats(conn: sqlite3.Connection) -> OverallStats:
    row = conn.execute(
        "SELECT COUNT(*) AS t, COALESCE(SUM(is_correct), 0) AS c FROM quiz_attempt"
    ).fetchone()
    return OverallStats(total=row["t"], correct=row["c"])


def direction_stats(conn: sqlite3.Connection) -> list[DirectionStats]:
    rows = conn.execute(
        """SELECT direction, COUNT(*) AS t, COALESCE(SUM(is_correct), 0) AS c
           FROM quiz_attempt GROUP BY direction ORDER BY direction"""
    ).fetchall()
    return [DirectionStats(direction=r["direction"], total=r["t"], correct=r["c"])
            for r in rows]


def daily_stats(conn: sqlite3.Connection, days: int = 7) -> list[DayStats]:
    rows = conn.execute(
        """SELECT substr(answered_at, 1, 10) AS day,
                  COUNT(*) AS t, COALESCE(SUM(is_correct), 0) AS c
           FROM quiz_attempt GROUP BY day ORDER BY day DESC LIMIT ?""",
        (days,),
    ).fetchall()
    return [DayStats(day=r["day"], total=r["t"], correct=r["c"]) for r in rows]


def _sense_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT s.id AS sense_id, w.spelling, s.meaning_ko,
                  COUNT(*) AS t, COALESCE(SUM(qa.is_correct), 0) AS c,
                  MAX(qa.answered_at) AS last_at
           FROM quiz_attempt qa
           JOIN sense s ON s.id = qa.sense_id
           JOIN word w ON w.id = s.word_id
           GROUP BY s.id"""
    ).fetchall()


def wrong_notes(conn: sqlite3.Connection, limit: int = 10) -> list[SenseStats]:
    """오답 노트: 한 번이라도 틀린 뜻을 오답 많은 순으로."""
    rows = [r for r in _sense_rows(conn) if r["t"] > r["c"]]
    rows.sort(key=lambda r: (-(r["t"] - r["c"]), r["c"] / r["t"]))
    return [
        SenseStats(sense_id=r["sense_id"], spelling=r["spelling"],
                   meaning_ko=r["meaning_ko"], total=r["t"], correct=r["c"],
                   last_answered_at=r["last_at"] or "")
        for r in rows[:limit]
    ]


def recent_attempts(conn: sqlite3.Connection, limit: int = 10) -> list[AttemptRecord]:
    rows = conn.execute(
        """SELECT qa.id, w.spelling, s.meaning_ko, qa.direction,
                  qa.is_correct, qa.answered_at
           FROM quiz_attempt qa
           JOIN sense s ON s.id = qa.sense_id
           JOIN word w ON w.id = s.word_id
           ORDER BY qa.answered_at DESC, qa.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [
        AttemptRecord(id=r["id"], spelling=r["spelling"], meaning_ko=r["meaning_ko"],
                      direction=r["direction"], is_correct=bool(r["is_correct"]),
                      answered_at=r["answered_at"])
        for r in rows
    ]
