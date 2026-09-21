import pytest

from vocab_note.db import get_connection, init_db
from vocab_note.vocab_service import (
    DuplicateWordError,
    SenseNotFoundError,
    VocabError,
    WordNotFoundError,
    add_sense,
    add_word,
    delete_sense,
    delete_word,
    get_word,
    get_word_by_spelling,
    list_words,
    normalize_spelling,
    update_sense,
    update_word_spelling,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "t.db"
    init_db(db_path)
    c = get_connection(db_path)
    yield c
    c.close()


def test_normalize():
    assert normalize_spelling("  Apple  ") == "apple"
    assert normalize_spelling("ice  CREAM") == "ice cream"


def test_add_word_and_sense(conn):
    w = add_word(conn, "apple")
    s = add_sense(conn, w.id, "noun", "사과", "I eat an apple.", "나는 사과를 먹는다.")
    got = get_word(conn, w.id)
    assert got.spelling == "apple"
    assert len(got.senses) == 1
    assert got.senses[0].meaning_ko == "사과"


def test_homonym_multi_sense(conn):
    """동음이의어: 한 단어에 뜻 여러 개."""
    w = add_word(conn, "bank")
    add_sense(conn, w.id, "noun", "은행")
    add_sense(conn, w.id, "noun", "둑")
    assert len(get_word(conn, w.id).senses) == 2


def test_duplicate_word_raises(conn):
    add_word(conn, "Apple")
    with pytest.raises(DuplicateWordError):
        add_word(conn, " apple ")


def test_meaning_required(conn):
    w = add_word(conn, "apple")
    with pytest.raises(VocabError):
        add_sense(conn, w.id, "noun", "   ")


def test_update_and_delete_sense(conn):
    w = add_word(conn, "apple")
    s = add_sense(conn, w.id, "noun", "사과")
    updated = update_sense(conn, s.id, meaning_ko="사과(과일)")
    assert updated.meaning_ko == "사과(과일)"
    delete_sense(conn, s.id)
    assert get_word(conn, w.id).senses == []
    with pytest.raises(SenseNotFoundError):
        delete_sense(conn, s.id)


def test_delete_word_cascades(conn):
    w = add_word(conn, "apple")
    add_sense(conn, w.id, "noun", "사과")
    delete_word(conn, w.id)
    with pytest.raises(WordNotFoundError):
        get_word(conn, w.id)
    assert list_words(conn) == []
    assert get_word_by_spelling(conn, "apple") is None


def test_rename_duplicate_raises(conn):
    a = add_word(conn, "apple")
    b = add_word(conn, "banana")
    with pytest.raises(DuplicateWordError):
        update_word_spelling(conn, b.id, "APPLE")
    renamed = update_word_spelling(conn, b.id, "grape")
    assert renamed.spelling == "grape"
    assert a.spelling == "apple"
