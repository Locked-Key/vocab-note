"""8단계: 고급 복습 서비스. 오답 빈도와 최근 풀이 기록을 바탕으로 복습 큐를 만듭니다.

- 로직: quiz_attempt에서 뜻(sense)별로 총 풀이 횟수, 틀린 횟수, 마지막 풀이 시각 집계
- 우선순위 점수 계산: (틀린 횟수 * 2) - (맞은 횟수) + (최근 틀렸을 때 가산점)
- UI와 독립된 순수 서비스 로직
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .quiz_service import QuizQuestion, build_quiz
from .vocab_service import VocabError


@dataclass
class ReviewItem:
    sense_id: int
    spelling: str
    meaning_ko: str
    total_attempts: int
    wrong_attempts: int
    correct_attempts: int
    last_answered_at: str
    priority_score: float

    @property
    def accuracy(self) -> float:
        return self.correct_attempts / self.total_attempts if self.total_attempts else 0.0


def get_review_queue(conn: sqlite3.Connection, limit: int = 10) -> list[ReviewItem]:
    """오답 우선순위가 높은 뜻 목록을 반환합니다."""
    rows = conn.execute(
        """SELECT s.id AS sense_id, w.spelling, s.meaning_ko,
                  COUNT(qa.id) AS total,
                  SUM(CASE WHEN qa.is_correct = 0 THEN 1 ELSE 0 END) AS wrongs,
                  SUM(CASE WHEN qa.is_correct = 1 THEN 1 ELSE 0 END) AS corrects,
                  MAX(qa.answered_at) AS last_at
           FROM sense s
           JOIN word w ON w.id = s.word_id
           JOIN quiz_attempt qa ON qa.sense_id = s.id
           GROUP BY s.id
           HAVING wrongs > 0
           ORDER BY wrongs DESC, (corrects * 1.0 / total) ASC, last_at ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    items = []
    for r in rows:
        wrongs = r["wrongs"] or 0
        corrects = r["corrects"] or 0
        total = r["total"] or 0
        # 우선순위 점수: 틀린 횟수 가중치 - 맞은 횟수
        score = (wrongs * 2.0) - corrects
        items.append(
            ReviewItem(
                sense_id=r["sense_id"],
                spelling=r["spelling"],
                meaning_ko=r["meaning_ko"],
                total_attempts=total,
                wrong_attempts=wrongs,
                correct_attempts=corrects,
                last_answered_at=r["last_at"] or "",
                priority_score=score,
            )
        )
    return items


def build_review_quiz(
    conn: sqlite3.Connection,
    limit: int = 5,
    choices: int = 4,
    seed: int | None = None,
) -> list[QuizQuestion]:
    """오답 우선순위 큐를 바탕으로 퀴즈 문제를 생성합니다."""
    queue = get_review_queue(conn, limit=limit)
    if not queue:
        # 오답 기록이 없으면 일반 퀴즈 풀에서 랜덤 출제
        return build_quiz(conn, num_questions=limit, choices=choices, seed=seed)

    sense_ids = {item.sense_id for item in queue}
    # 해당 sense들을 포함하도록 퀴즈 구성
    all_sense_rows = conn.execute(
        """SELECT s.*, w.spelling FROM sense s
           JOIN word w ON w.id = s.word_id
           WHERE s.meaning_ko <> ''"""
    ).fetchall()
    
    # review 대상 sense 행들 필터링
    target_rows = [r for r in all_sense_rows if r["id"] in sense_ids]
    if not target_rows:
        return build_quiz(conn, num_questions=limit, choices=choices, seed=seed)

    import random
    rng = random.Random(seed)
    rng.shuffle(target_rows)
    picked_rows = target_rows[:limit]

    questions: list[QuizQuestion] = []
    pool_rows = all_sense_rows
    for row in picked_rows:
        d = rng.choice(["en_to_ko", "ko_to_en"])
        if d == "en_to_ko":
            prompt, answer = row["spelling"], row["meaning_ko"].strip()
            distract = [r["meaning_ko"].strip() for r in pool_rows]
        else:
            pos = f"({row['part_of_speech']}) " if row["part_of_speech"] else ""
            prompt, answer = f"{pos}{row['meaning_ko'].strip()}", row["spelling"]
            distract = [r["spelling"] for r in pool_rows]

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
