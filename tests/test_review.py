import pytest

from vocab_note.db import get_connection, init_db
from vocab_note.review_service import build_review_quiz, get_review_queue
from vocab_note.vocab_service import add_sense, add_word


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "t.db"
    init_db(db_path)
    c = get_connection(db_path)
    yield c
    c.close()


def test_review_queue_sorts_by_wrongs(conn):
    w1 = add_word(conn, "apple")
    s1 = add_sense(conn, w1.id, "noun", "사과")
    w2 = add_word(conn, "banana")
    s2 = add_sense(conn, w2.id, "noun", "바나나")

    # apple 2번 틀림, banana 1번 틀림
    for _ in range(2):
        conn.execute("INSERT INTO quiz_attempt (sense_id, direction, is_correct) VALUES (?, 'en_to_ko', 0)", (s1.id,))
    conn.execute("INSERT INTO quiz_attempt (sense_id, direction, is_correct) VALUES (?, 'en_to_ko', 0)", (s2.id,))
    conn.commit()

    queue = get_review_queue(conn)
    assert len(queue) == 2
    assert queue[0].sense_id == s1.id  # 오답 많은 apple이 우선순위 1위


def test_build_review_quiz_falls_back_when_no_wrongs(conn):
    w1 = add_word(conn, "apple")
    add_sense(conn, w1.id, "noun", "사과")
    # 오답 기록 없으면 일반 퀴즈로 폴백
    q = build_review_quiz(conn, limit=1, seed=1)
    assert len(q) == 1
    assert q[0].answer == "사과"
