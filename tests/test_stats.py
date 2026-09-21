import pytest

from vocab_note.db import get_connection, init_db
from vocab_note.stats_service import (
    daily_stats,
    direction_stats,
    overall_stats,
    recent_attempts,
    wrong_notes,
)
from vocab_note.vocab_service import add_sense, add_word


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "t.db"
    init_db(db_path)
    c = get_connection(db_path)
    yield c
    c.close()


@pytest.fixture()
def history(conn):
    """apple: 2/3 정답 / banana: 0/2 정답, 날짜를 섞어서 기록."""
    apple = add_word(conn, "apple")
    a = add_sense(conn, apple.id, "noun", "사과")
    banana = add_word(conn, "banana")
    b = add_sense(conn, banana.id, "noun", "바나나")
    rows = [
        (a.id, "en_to_ko", 1, "2026-09-20 10:00:00"),
        (a.id, "en_to_ko", 0, "2026-09-20 11:00:00"),
        (a.id, "ko_to_en", 1, "2026-09-21 09:00:00"),
        (b.id, "en_to_ko", 0, "2026-09-21 09:30:00"),
        (b.id, "ko_to_en", 0, "2026-09-21 10:00:00"),
    ]
    for sense_id, direction, correct, at in rows:
        conn.execute(
            """INSERT INTO quiz_attempt (sense_id, direction, is_correct, answered_at)
               VALUES (?, ?, ?, ?)""",
            (sense_id, direction, correct, at),
        )
    conn.commit()
    return conn


def test_overall_and_direction(history):
    o = overall_stats(history)
    assert (o.total, o.correct) == (5, 2)
    assert o.accuracy == pytest.approx(0.4)
    by_dir = {d.direction: d for d in direction_stats(history)}
    assert (by_dir["en_to_ko"].total, by_dir["en_to_ko"].correct) == (3, 1)
    assert (by_dir["ko_to_en"].total, by_dir["ko_to_en"].correct) == (2, 1)


def test_daily(history):
    days = {d.day: d for d in daily_stats(history)}
    assert set(days) == {"2026-09-20", "2026-09-21"}
    assert (days["2026-09-20"].total, days["2026-09-20"].correct) == (2, 1)
    assert days["2026-09-21"].accuracy == pytest.approx(1 / 3)


def test_wrong_notes_order(history):
    wrongs = wrong_notes(history)
    assert [w.spelling for w in wrongs] == ["banana", "apple"]  # 오답 많은 순
    assert wrongs[0].wrong == 2 and wrongs[0].accuracy == 0.0
    assert wrongs[1].wrong == 1


def test_recent_attempts_order(history):
    recents = recent_attempts(history, limit=2)
    assert [r.spelling for r in recents] == ["banana", "banana"]
    assert recents[0].answered_at == "2026-09-21 10:00:00"
    assert recents[0].is_correct is False


def test_empty_db():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "e.db"
        init_db(db)
        conn = get_connection(db)
        try:
            o = overall_stats(conn)
            assert (o.total, o.correct, o.accuracy) == (0, 0, 0.0)
            assert direction_stats(conn) == []
            assert daily_stats(conn) == []
            assert wrong_notes(conn) == []
            assert recent_attempts(conn) == []
        finally:
            conn.close()
