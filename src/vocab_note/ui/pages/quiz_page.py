"""퀴즈 본문 페이지: 설정 → 문제 → 결과 3단.

ReviewPage가 이 클래스를 상속해 설정 화면과 출제 함수만 바꿔 씁니다.
출제·채점·기록은 quiz_service 함수만 사용합니다.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...db import get_connection
from ...quiz_service import QuizError, QuizSession, build_quiz, record_attempt
from ...tag_service import list_tags

ALL_TAGS = "전체 태그"
DIRECTION_LABELS = {
    "both": "섞어서",
    "en_to_ko": "영어 보고 뜻 맞히기",
    "ko_to_en": "뜻 보고 영어 맞히기",
}


class QuizPage(QWidget):
    title_text = "퀴즈"

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self._db_path = db_path
        self.session: QuizSession | None = None

        self.pages = QStackedWidget()
        self.pages.addWidget(self._setup_page())     # 0
        self.pages.addWidget(self._question_page())  # 1
        self.pages.addWidget(self._result_page())    # 2

        layout = QVBoxLayout()
        layout.addWidget(self.pages)
        self.setLayout(layout)

    def _conn(self):
        return get_connection(self._db_path)

    # -- 페이지 진입/초기화 -----------------------------------------------
    def reset(self) -> None:
        """사이드바로 이 페이지에 들어올 때마다 설정 화면부터."""
        self.session = None
        self.refresh_setup()
        self.pages.setCurrentIndex(0)

    def refresh_setup(self) -> None:
        prev = self.tag_box.currentText()
        conn = self._conn()
        try:
            names = sorted(t.name for t, _ in list_tags(conn))
        finally:
            conn.close()
        self.tag_box.blockSignals(True)
        self.tag_box.clear()
        self.tag_box.addItem(ALL_TAGS)
        self.tag_box.addItems(names)
        if prev in names:
            self.tag_box.setCurrentText(prev)
        self.tag_box.blockSignals(False)

    # -- 0: 설정 ----------------------------------------------------------
    def _setup_page(self) -> QWidget:
        heading = QLabel("퀴즈 설정")
        font = heading.font()
        font.setPointSize(18)
        font.setBold(True)
        heading.setFont(font)

        self.tag_box = QComboBox()
        self.tag_box.addItem(ALL_TAGS)
        self.direction_box = QComboBox()
        self.direction_box.addItems(list(DIRECTION_LABELS))
        self.direction_box.setCurrentText("both")
        self.num_box = QSpinBox()
        self.num_box.setRange(1, 50)
        self.num_box.setValue(5)
        self.start_btn = QPushButton("시작")
        self.start_btn.clicked.connect(self._on_start_clicked)

        layout = QVBoxLayout()
        layout.addWidget(heading)
        layout.addSpacing(8)
        layout.addWidget(QLabel("출제 범위"))
        layout.addWidget(self.tag_box)
        layout.addWidget(QLabel("방향"))
        layout.addWidget(self.direction_box)
        layout.addWidget(QLabel("문제 수"))
        layout.addWidget(self.num_box)
        layout.addStretch(1)
        layout.addWidget(self.start_btn)
        page = QWidget()
        page.setLayout(layout)
        self.refresh_setup()
        return page

    def _on_start_clicked(self) -> None:
        self.start(self.tag_box.currentText(),
                   self.direction_box.currentText(),
                   self.num_box.value())

    def _build_questions(self, conn, tag: str, direction: str, num: int, seed):
        """서브클래스가 바꿔 끼우는 출제 함수."""
        return build_quiz(conn, "" if tag == ALL_TAGS else tag,
                          direction, num, seed=seed)

    def start(self, tag: str = ALL_TAGS, direction: str = "both",
              num: int = 5, seed=None) -> bool:
        """퀴즈 시작. 테스트에서 seed를 주면 순서 재현 가능."""
        conn = self._conn()
        try:
            questions = self._build_questions(conn, tag, direction, num, seed)
        except QuizError as e:
            QMessageBox.warning(self, "출제 불가", str(e))
            return False
        finally:
            conn.close()
        self.session = QuizSession(questions)
        self._render_question()
        self.pages.setCurrentIndex(1)
        return True

    # -- 1: 문제 -----------------------------------------------------------
    def _question_page(self) -> QWidget:
        self.progress = QLabel("")
        self.prompt = QLabel("")
        font = self.prompt.font()
        font.setPointSize(22)
        font.setBold(True)
        self.prompt.setFont(font)
        self.prompt.setWordWrap(True)
        self.hint = QLabel("")
        self.option_box = QVBoxLayout()
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        self.next_btn = QPushButton("다음")
        self.next_btn.clicked.connect(self.on_next)
        self.quit_btn = QPushButton("그만두기")
        self.quit_btn.clicked.connect(self.reset)

        bottom = QHBoxLayout()
        bottom.addWidget(self.quit_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.next_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.progress)
        layout.addWidget(self.prompt)
        layout.addWidget(self.hint)
        layout.addLayout(self.option_box)
        layout.addWidget(self.feedback)
        layout.addStretch(1)
        layout.addLayout(bottom)
        page = QWidget()
        page.setLayout(layout)
        return page

    def _clear_options(self) -> None:
        while self.option_box.count():
            item = self.option_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_question(self) -> None:
        q = self.session.current
        n = self.session.index + 1
        self.progress.setText(f"[{n}/{self.session.total}]")
        self.prompt.setText(q.prompt)
        self.hint.setText("뜻은?" if q.direction == "en_to_ko" else "영어는?")
        self.feedback.setText("")
        self.next_btn.setEnabled(False)
        self._clear_options()
        self.option_buttons: list[QPushButton] = []
        for opt in q.options:
            btn = QPushButton(opt)
            btn.clicked.connect(lambda _=False, o=opt: self.on_pick(o))
            self.option_box.addWidget(btn)
            self.option_buttons.append(btn)

    def on_pick(self, picked: str) -> None:
        q = self.session.current
        correct = self.session.answer_current(picked)
        conn = self._conn()
        try:
            record_attempt(conn, q.sense_id, q.direction, correct)
        finally:
            conn.close()
        for btn in self.option_buttons:
            btn.setEnabled(False)
            if btn.text() == q.answer:
                btn.setStyleSheet("background-color: #2e7d32; color: white;")
            elif btn.text() == picked:
                btn.setStyleSheet("background-color: #c62828; color: white;")
        self.feedback.setText("정답!" if correct else f"오답. 정답: {q.answer}")
        self.next_btn.setText("결과 보기" if self.session.done else "다음")
        self.next_btn.setEnabled(True)

    def on_next(self) -> None:
        if self.session.done:
            self._render_result()
            self.pages.setCurrentIndex(2)
        else:
            self._render_question()

    # -- 2: 결과 ------------------------------------------------------------
    def _result_page(self) -> QWidget:
        self.score_label = QLabel("")
        font = self.score_label.font()
        font.setPointSize(18)
        font.setBold(True)
        self.score_label.setFont(font)
        self.review = QListWidget()
        again = QPushButton("다시 풀기")
        again.clicked.connect(self.reset)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(again)
        layout = QVBoxLayout()
        layout.addWidget(self.score_label)
        layout.addWidget(self.review, 1)
        layout.addLayout(bottom)
        page = QWidget()
        page.setLayout(layout)
        return page

    def _render_result(self) -> None:
        self.score_label.setText(f"점수: {self.session.score}/{self.session.total}")
        self.review.clear()
        for q, picked, correct in self.session.results:
            mark = "O" if correct else "X"
            extra = "" if correct else f" (선택: {picked})"
            QListWidgetItem(f"[{mark}] {q.prompt} → {q.answer}{extra}", self.review)
