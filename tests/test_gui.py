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


def test_sidebar_has_five_menus_and_switches_pages(tmp_path):
    win = _window(tmp_path)
    labels = [win.sidebar.item(i).text() for i in range(win.sidebar.count())]
    assert len(labels) == 5
    for name in ("단어장", "퀴즈", "복습", "기록", "설정"):
        assert any(name in lab for lab in labels)

    assert win.stack.currentWidget() is win.vocab_page
    win.go_to_page("퀴즈")
    assert win.stack.currentWidget() is win.quiz_page
    assert win.quiz_page.pages.currentIndex() == 0  # 진입 시 설정 화면부터
    win.go_to_page("복습")
    assert win.stack.currentWidget() is win.review_page
    win.go_to_page("기록")
    assert win.stack.currentWidget() is win.stats_page
    win.go_to_page("설정")
    assert win.stack.currentWidget() is win.settings_page
    win.go_to_page("단어장")
    assert win.stack.currentWidget() is win.vocab_page
    # 기존 호환 메서드도 페이지 이동으로 동작
    win.open_quiz()
    assert win.stack.currentWidget() is win.quiz_page
    win.open_settings()
    assert win.stack.currentWidget() is win.settings_page


def test_review_page_shows_queue_and_starts(tmp_path):
    from vocab_note.db import get_connection

    win = _window(tmp_path)
    db_path = tmp_path / "gui.db"
    conn = get_connection(db_path)
    try:
        sense_id = conn.execute("SELECT id FROM sense ORDER BY id").fetchone()["id"]
        conn.execute(
            "INSERT INTO quiz_attempt (sense_id, direction, is_correct) VALUES (?, 'en_to_ko', 0)",
            (sense_id,))
        conn.commit()
    finally:
        conn.close()
    win.go_to_page("복습")
    assert win.review_page.queue_list.count() == 1
    assert "오답 1회" in win.review_page.queue_list.item(0).text()
    assert win.review_page.start(num=1, seed=3) is True
    assert win.review_page.session.total == 1
    assert win.review_page.session.current.sense_id == sense_id


def test_stats_page_renders(tmp_path):
    win = _window(tmp_path)
    win.go_to_page("기록")
    assert "아직 푼 문제가 없습니다" in win.stats_page.overall_label.text()
    assert win.stats_page.wrong_list.count() == 1  # "(오답 없음)" 플레이스홀더


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


def test_dialog_accept_code_regression():
    """회귀: dlg.Accepted(인스턴스 접근)는 PySide6에서 AttributeError.
    QDialog.DialogCode.Accepted(클래스 접근)를 써야 함."""
    from PySide6.QtWidgets import QDialog

    from vocab_note.ui.dialogs import SenseDialog, WordDialog

    QApplication.instance() or QApplication([])
    assert QDialog.DialogCode.Accepted is not None

    dlg = WordDialog()
    dlg.spelling.setText("apple")
    dlg.meaning.setText("사과")
    dlg.tags.setText("과일, 토익")
    dlg._on_ok()  # OK 버튼과 같은 경로 (메시지박스 없이 accept)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.data() == {
        "spelling": "apple", "pos": "", "meaning": "사과",
        "ex_en": "", "ex_ko": "", "tags": ["과일", "토익"],
    }

    sense = SenseDialog(initial={"meaning_ko": "사과"})
    sense._on_ok()
    assert sense.result() == QDialog.DialogCode.Accepted


def test_word_dialog_ai_suggest_fills_from_mock(monkeypatch, tmp_path):
    """AI 추천 버튼: Mock 제안이 폼에 채워짐 (저장은 확인 버튼)."""
    import os

    from vocab_note.ui.dialogs import WordDialog

    QApplication.instance() or QApplication([])
    monkeypatch.setattr("vocab_note.ai.service.DOTENV_PATH", tmp_path / ".env")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    dlg = WordDialog()
    dlg.spelling.setText("apple")
    dlg._on_ai_suggest()
    assert "apple" in dlg.meaning.text()
    assert dlg.pos.text() == "noun"
    assert dlg.ex_en.text() != ""


def test_settings_dialog_opens(tmp_path):
    from vocab_note.ui.settings_dialog import SettingsDialog

    QApplication.instance() or QApplication([])
    dlg = SettingsDialog()
    assert "gemini" in [dlg.provider_box.itemText(i)
                        for i in range(dlg.provider_box.count())]
    dlg.provider_box.setCurrentText("openai")
    assert "gpt-4o-mini" in dlg.model_edit.placeholderText()
