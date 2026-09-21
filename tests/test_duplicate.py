import vocab_note.cli as cli
from vocab_note.db import get_connection, init_db
from vocab_note.vocab_service import add_sense, add_word, find_duplicate


def _tmp_conn(monkeypatch, tmp_path):
    """CLI의 get_connection을 tmp DB로 돌리는 헬퍼."""
    db_path = tmp_path / "dup.db"
    init_db(db_path)

    def fake(*args, **kwargs):
        return get_connection(db_path)

    monkeypatch.setattr(cli, "get_connection", fake)
    return db_path


def test_find_duplicate_case_and_space_insensitive(tmp_path):
    db_path = tmp_path / "t.db"
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        w = add_word(conn, "Apple")
        add_sense(conn, w.id, "noun", "사과")
        for variant in ["apple", " APPLE ", "  apple  ", "Apple"]:
            dup = find_duplicate(conn, variant)
            assert dup is not None and dup.id == w.id
        assert find_duplicate(conn, "banana") is None
        assert find_duplicate(conn, "   ") is None
    finally:
        conn.close()


def test_cli_add_duplicate_with_flag_adds_sense(monkeypatch, tmp_path, capsys):
    _tmp_conn(monkeypatch, tmp_path)
    cli.main(["add", "bank", "--pos", "noun", "--meaning", "은행"])
    capsys.readouterr()
    # 대소문자·공백이 달라도 중복으로 잡고, --add-sense면 뜻으로 추가
    cli.main(["add", "  BANK ", "--pos", "noun", "--meaning", "둑", "--add-sense"])
    out = capsys.readouterr().out
    assert "중복 경고" in out

    conn = get_connection(tmp_path / "dup.db")
    try:
        words = conn.execute("SELECT COUNT(*) c FROM word").fetchone()["c"]
        senses = conn.execute("SELECT COUNT(*) c FROM sense").fetchone()["c"]
        assert words == 1  # 단어 행은 그대로 1개
        assert senses == 2  # 뜻만 2개
    finally:
        conn.close()


def test_cli_add_duplicate_without_flag_cancels(monkeypatch, tmp_path, capsys):
    _tmp_conn(monkeypatch, tmp_path)
    cli.main(["add", "apple", "--meaning", "사과"])
    capsys.readouterr()
    # 파이프(비대화형)에서는 취소되고 단어/뜻이 늘지 않아야 함
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    cli.main(["add", "APPLE", "--meaning", "사과2"])
    out = capsys.readouterr().out
    assert "중복 경고" in out
    assert "취소됨" in out

    conn = get_connection(tmp_path / "dup.db")
    try:
        senses = conn.execute("SELECT COUNT(*) c FROM sense").fetchone()["c"]
        assert senses == 1
    finally:
        conn.close()
