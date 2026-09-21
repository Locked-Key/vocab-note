import pytest

from vocab_note.db import get_connection, init_db
from vocab_note.tag_service import (
    TagError,
    get_or_create_tag,
    get_word_tags,
    list_tags,
    normalize_tag_name,
    search_words,
    tag_word,
    untag_word,
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
def seeded(conn):
    """apple(과일), banana(과일), run(동사)을 심어둠."""
    apple = add_word(conn, "apple")
    add_sense(conn, apple.id, "noun", "사과")
    banana = add_word(conn, "banana")
    add_sense(conn, banana.id, "noun", "바나나")
    run = add_word(conn, "run")
    add_sense(conn, run.id, "verb", "달리다")
    tag_word(conn, apple.id, "과일")
    tag_word(conn, banana.id, "과일")
    tag_word(conn, run.id, "동사")
    return {"apple": apple, "banana": banana, "run": run}


def test_normalize_tag_name():
    assert normalize_tag_name("  과일  ") == "과일"
    assert normalize_tag_name("toeic  vocab") == "toeic vocab"


def test_tag_case_insensitive_duplicate(conn):
    a = get_or_create_tag(conn, "TOEIC")
    b = get_or_create_tag(conn, " toeic ")
    assert a.id == b.id
    with pytest.raises(TagError):
        get_or_create_tag(conn, "   ")


def test_tag_word_idempotent(conn, seeded):
    tag_word(conn, seeded["apple"].id, "과일")  # 중복 부착해도 1개 유지
    tags = get_word_tags(conn, seeded["apple"].id)
    assert [t.name for t in tags] == ["과일"]


def test_untag_word(conn, seeded):
    untag_word(conn, seeded["apple"].id, "과일")
    assert get_word_tags(conn, seeded["apple"].id) == []
    with pytest.raises(TagError):
        untag_word(conn, seeded["apple"].id, "과일")  # 이미 없음
    # 태그 자체는 남아 있음
    assert any(t.name == "과일" for t, _ in list_tags(conn))


def test_list_tags_counts(conn, seeded):
    counts = {t.name: c for t, c in list_tags(conn)}
    assert counts == {"과일": 2, "동사": 1}


def test_search_by_spelling_and_meaning(conn, seeded):
    assert [w.spelling for w in search_words(conn, "app")] == ["apple"]
    assert [w.spelling for w in search_words(conn, "바나나")] == ["banana"]
    assert [w.spelling for w in search_words(conn, "사과")] == ["apple"]
    assert search_words(conn, "없는단어") == []


def test_filter_by_tag(conn, seeded):
    got = search_words(conn, tag="과일")
    assert sorted(w.spelling for w in got) == ["apple", "banana"]
    assert [w.spelling for w in search_words(conn, tag="동사")] == ["run"]
    # 대소문자 무시
    tag_word(conn, seeded["run"].id, "TOEIC")
    assert [w.spelling for w in search_words(conn, tag="toeic")] == ["run"]


def test_search_plus_tag(conn, seeded):
    got = search_words(conn, query="a", tag="과일")
    assert sorted(w.spelling for w in got) == ["apple", "banana"]
    got = search_words(conn, query="run", tag="과일")
    assert got == []


def test_order_recent(conn, seeded):
    got = search_words(conn, order="recent")
    assert [w.spelling for w in got] == ["run", "banana", "apple"]
    got = search_words(conn, order="alpha")
    assert [w.spelling for w in got] == ["apple", "banana", "run"]
    with pytest.raises(TagError):
        search_words(conn, order="wrong")


def test_search_result_has_senses_and_tags(conn, seeded):
    (apple,) = [w for w in search_words(conn, "apple")]
    assert [s.meaning_ko for s in apple.senses] == ["사과"]
    assert [t.name for t in apple.tags] == ["과일"]
