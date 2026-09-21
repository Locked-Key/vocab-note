"""5단계: 퀴즈 서비스. UI와 독립 — CLI·GUI 어디서든 같은 함수를 씁니다.

- 출제: `build_quiz` (태그 범위 + 방향 + 객관식 보기 생성, random)
- 상태: `QuizSession` (현재 문제·점수·풀이 기록)
- 기록: `record_attempt` (quiz_attempt 테이블에 저장 → 6단계 통계의 재료)
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass, field

from .tag_service import normalize_tag_name
from .vocab_service import VocabError

DIRECTIONS = ("en_to_ko", "ko_to_en")


class QuizError(VocabError):
    pass


@dataclass
class QuizQuestion:
    sense_id: int
    direction: str  # en_to_ko: 영어 보고 뜻 고르기 / ko_to_en: 뜻 보고 영어 고르기
    prompt: str
    options: list[str]
    answer: str  # 정답 (options 중 하나)


@dataclass
class QuizSession:
    """풀이 상태. UI는 current/score/done만 읽고 answer_current로 진행."""

    questions: list[QuizQuestion]
    index: int = 0
    correct_count: int = 0
    results: list[tuple[QuizQuestion, str, bool]] = field(default_factory=list)

    @property
    def current(self) -> QuizQuestion | None:
        return self.questions[self.index] if self.index < len(self.questions) else None

    @property
    def done(self) -> bool:
        return self.index >= len(self.questions)

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def score(self) -> int:
        return self.correct_count

    def answer_current(self, picked: str) -> bool:
        q = self.current
        if q is None:
            raise QuizError("남은 문제가 없습니다.")
        correct = picked == q.answer
        self.results.append((q, picked, correct))
        if correct:
            self.correct_count += 1
        self.index += 1
        return correct


def _pool(conn: sqlite3.Connection, tag: str) -> list[sqlite3.Row]:
    """출제 후보 sense 목록 (뜻 비어있지 않은 것만)."""
    if tag:
        rows = conn.execute(
            """SELECT s.*, w.spelling FROM sense s
               JOIN word w ON w.id = s.word_id
               JOIN word_tag wt ON wt.word_id = w.id
               JOIN tag t ON t.id = wt.tag_id
               WHERE t.name = ? COLLATE NOCASE
               AND s.meaning_ko <> '' ORDER BY s.id""",
            (tag,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT s.*, w.spelling FROM sense s
               JOIN word w ON w.id = s.word_id
               WHERE s.meaning_ko <> '' ORDER BY s.id"""
        ).fetchall()
    return rows


def build_quiz(
    conn: sqlite3.Connection,
    tag: str = "",
    direction: str = "both",
    num_questions: int = 5,
    choices: int = 4,
    seed: int | None = None,
) -> list[QuizQuestion]:
    """문제 생성. seed를 주면 동일 순서로 재현 (테스트용)."""
    if direction not in ("en_to_ko", "ko_to_en", "both"):
        raise QuizError("direction은 en_to_ko / ko_to_en / both 중 하나여야 합니다.")
    if num_questions < 1:
        raise QuizError("num_questions는 1 이상이어야 합니다.")
    if choices < 2:
        raise QuizError("choices는 2 이상이어야 합니다.")
    t = normalize_tag_name(tag) if tag.strip() else ""
    rng = random.Random(seed)

    pool = _pool(conn, t)
    if not pool:
        raise QuizError("출제할 단어가 없습니다. (태그에 단어가 있나요?)")
    order = list(pool)
    rng.shuffle(order)
    picked_rows = order[:num_questions]

    questions: list[QuizQuestion] = []
    for row in picked_rows:
        d = direction if direction != "both" else rng.choice(list(DIRECTIONS))
        if d == "en_to_ko":
            prompt, answer = row["spelling"], row["meaning_ko"].strip()
            distract = [r["meaning_ko"].strip() for r in pool]
        else:
            pos = f"({row['part_of_speech']}) " if row["part_of_speech"] else ""
            prompt, answer = f"{pos}{row['meaning_ko'].strip()}", row["spelling"]
            distract = [r["spelling"] for r in pool]
        # 오답 보기: 정답·빈값·중복 제외 후 랜덤 샘플
        seen = {answer, ""}
        options = [answer]
        cands = [c for c in distract if c not in seen]
        rng.shuffle(cands)
        for c in cands:
            if len(options) >= choices:
                break
            if c not in seen:
                seen.add(c)
                options.append(c)
        rng.shuffle(options)
        questions.append(
            QuizQuestion(
                sense_id=row["id"], direction=d, prompt=prompt,
                options=options, answer=answer,
            )
        )
    return questions


def record_attempt(
    conn: sqlite3.Connection, sense_id: int, direction: str, is_correct: bool
) -> int:
    """풀이 1건을 quiz_attempt에 저장하고 id를 반환."""
    if direction not in DIRECTIONS:
        raise QuizError(f"direction 오류: {direction}")
    cur = conn.execute(
        "INSERT INTO quiz_attempt (sense_id, direction, is_correct) VALUES (?, ?, ?)",
        (sense_id, direction, 1 if is_correct else 0),
    )
    conn.commit()
    return cur.lastrowid
