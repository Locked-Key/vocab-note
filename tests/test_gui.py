"""4단계: GUI 스모크 테스트 (offscreen — 창을 띄우지 않고 검증)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vocab_note.db import init_db
from vocab_note.tag_service import tag_word
from vocab_note.ui.main_window import MainWindow
from vocab_note.ui.theme import apply_theme
from vocab_note.vocab_service import add_sense, add_word


def _seed(db_path):
    from vocab_note.db import get_connection

    init_db(db_path)
    conn = get_connection(db_path)
    try:
        apple = add_word(conn, "apple")
        add_sense(conn, apple.id, "noun", "사과")
        run = add_word(conn, "run")
        add_sense(conn, run.id, "verb", "달리다")
        tag_word(conn, apple.id, "과일")
    finally:
        conn.close()


def _window(tmp_path):
    QApplication.instance() or QApplication([])
    db_path = tmp_path / "gui.db"
    _seed(db_path)
    return MainWindow(db_path=db_path)


def test_main_window_lists_words(tmp_path):
    win = _window(tmp_path)
    assert win.word_list.count() == 2
    assert "과일" in [
        win.tag_filter.itemText(i) for i in range(win.tag_filter.count())
    ]


def test_search_and_tag_filter(tmp_path):
    win = _window(tmp_path)
    win.search.setText("app")
    assert win.word_list.count() == 1
    win.search.setText("")
    win.tag_filter.setCurrentText("과일")
    assert win.word_list.count() == 1


def test_detail_shows_senses(tmp_path):
    win = _window(tmp_path)
    win.word_list.setCurrentRow(0)  # alpha순: apple
    assert win.title.text() == "apple"
    assert win.sense_list.count() == 1
    assert "사과" in win.sense_detail.text()


def test_dark_toggle_changes_stylesheet(tmp_path):
    win = _window(tmp_path)
    app = QApplication.instance()
    apply_theme(app, dark=False)
    light = app.styleSheet()
    win.dark_toggle.setChecked(True)
    assert app.styleSheet() != light
    assert win._dark is True


def test_ui_has_no_sql():
    """UI-로직 분리: ui 패키지에 SQL 문자열이 없어야 함."""
    ui_dir = Path(__file__).resolve().parent.parent / "src" / "vocab_note" / "ui"
    hits = [
        p.name
        for p in ui_dir.glob("*.py")
        if any(
            kw in p.read_text(encoding="utf-8")
            for kw in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ")
        )
    ]
    assert hits == []


def _quiz_seed(db_path):
    from vocab_note.db import get_connection
    from vocab_note.tag_service import tag_word
    from vocab_note.vocab_service import add_sense, add_word

    init_db(db_path)
    conn = get_connection(db_path)
    try:
        for spelling, meaning in [("apple", "사과"), ("banana", "바나나"),
                                  ("grape", "포도"), ("peach", "복숭아")]:
            w = add_word(conn, spelling)
            add_sense(conn, w.id, "noun", meaning)
            tag_word(conn, w.id, "과일")
    finally:
        conn.close()


def test_main_window_has_quiz_button(tmp_path):
    win = _window(tmp_path)
    assert win.quiz_btn.text() == "퀴즈"


def test_quiz_dialog_full_flow(tmp_path):
    from vocab_note.db import get_connection
    from vocab_note.ui.quiz_dialog import QuizDialog

    QApplication.instance() or QApplication([])
    db_path = tmp_path / "q.db"
    _quiz_seed(db_path)

    dlg = QuizDialog(db_path=db_path)
    assert dlg.pages.currentIndex() == 0
    assert dlg.start("전체 태그", "both", 2, seed=11) is True
    assert dlg.pages.currentIndex() == 1
    assert dlg.session.total == 2

    # 1번 문제: 정답 버튼 클릭
    q1 = dlg.session.current
    [b for b in dlg.option_buttons if b.text() == q1.answer][0].click()
    assert "정답" in dlg.feedback.text()
    assert dlg.next_btn.isEnabled()
    dlg.next_btn.click()

    # 2번 문제: 오답 버튼 클릭
    q2 = dlg.session.current
    wrong = [b for b in dlg.option_buttons if b.text() != q2.answer][0]
    wrong.click()
    assert "오답" in dlg.feedback.text()
    dlg.next_btn.click()

    assert dlg.pages.currentIndex() == 2
    assert dlg.score_label.text() == "점수: 1/2"
    assert dlg.review.count() == 2

    # 풀이 2건이 DB에 기록됐는지
    conn = get_connection(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) c FROM quiz_attempt").fetchone()["c"]
        assert n == 2
    finally:
        conn.close()
