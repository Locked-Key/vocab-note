from vocab_note.db import init_db, list_tables


def test_init_db_creates_all_tables(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    tables = set(list_tables(db_path))
    assert {"word", "sense", "tag", "word_tag", "quiz_attempt"} <= tables
