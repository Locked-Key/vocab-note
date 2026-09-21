import pytest

from vocab_note.db import get_connection, init_db
from vocab_note.quiz_service import (
    QuizError,
    QuizSession,
    build_quiz,
    record_attempt,
)
from vocab_note.tag_service import tag_word
from vocab_note.vocab_service import add_sense, add_word


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "t.db"
    init_db(db_path)
    c = get_connection(db_path)
    yield c
    c.close()


@pytest.fixture()
def seeded(conn):
    data = [("apple", "noun", "사과"), ("banana", "noun", "바나나"),
            ("run", "verb", "달리다"), ("grape", "noun", "포도"),
            ("peach", "noun", "복숭아")]
    for spelling, pos, meaning in data:
        w = add_word(conn, spelling)
        add_sense(conn, w.id, pos, meaning)
        tag_word(conn, w.id, "과일" if spelling != "run" else "동사")
    return conn


def test_build_quiz_same_seed_same_order(seeded):
    a = build_quiz(seeded, num_questions=3, seed=42)
    b = build_quiz(seeded, num_questions=3, seed=42)
    assert [(q.prompt, q.answer) for q in a] == [(q.prompt, q.answer) for q in b]


def test_options_contain_answer_no_duplicates(seeded):
    for q in build_quiz(seeded, num_questions=5, seed=1):
        assert q.answer in q.options
        assert len(q.options) == len(set(q.options))  # 중복 보기 없음
        assert 2 <= len(q.options) <= 4


def test_direction_modes(seeded):
    for q in build_quiz(seeded, direction="en_to_ko", num_questions=5, seed=2):
        assert q.direction == "en_to_ko"
    for q in build_quiz(seeded, direction="ko_to_en", num_questions=5, seed=2):
        assert q.direction == "ko_to_en"


def test_tag_scope(seeded):
    got = build_quiz(seeded, tag="동사", num_questions=5, seed=3)
    assert len(got) == 1  # run만
    got = build_quiz(seeded, tag="과일", num_questions=5, seed=3)
    assert len(got) == 4
    with pytest.raises(QuizError):
        build_quiz(seeded, tag="없는태그", seed=3)


def test_empty_db_raises(tmp_path):
    init_db(tmp_path / "e.db")
    conn = get_connection(tmp_path / "e.db")
    try:
        with pytest.raises(QuizError):
            build_quiz(conn, seed=0)
    finally:
        conn.close()


def test_session_scoring(seeded):
    questions = build_quiz(seeded, num_questions=2, seed=7)
    s = QuizSession(questions)
    assert not s.done and s.total == 2
    assert s.answer_current(questions[0].answer) is True
    assert s.answer_current("절대정답아님") is False
    assert s.done and s.score == 1
    assert len(s.results) == 2


def test_record_attempt_writes_row(seeded):
    q = build_quiz(seeded, num_questions=1, seed=9)[0]
    row_id = record_attempt(seeded, q.sense_id, q.direction, True)
    row = seeded.execute(
        "SELECT * FROM quiz_attempt WHERE id = ?", (row_id,)).fetchone()
    assert row["sense_id"] == q.sense_id
    assert row["direction"] == q.direction
    assert row["is_correct"] == 1


def test_invalid_args(seeded):
    with pytest.raises(QuizError):
        build_quiz(seeded, direction="wrong")
    with pytest.raises(QuizError):
        build_quiz(seeded, num_questions=0)
    with pytest.raises(QuizError):
        record_attempt(seeded, 1, "wrong", True)
