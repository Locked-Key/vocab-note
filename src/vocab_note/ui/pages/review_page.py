"""복습 본문 페이지: 오답 우선순위 큐를 보여주고 바로 복습 퀴즈로.

출제는 review_service.build_review_quiz만 사용합니다 (오답 없으면 일반 퀴즈로 폴백).
"""

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...review_service import build_review_quiz, get_review_queue
from .quiz_page import QuizPage


class ReviewPage(QuizPage):
    title_text = "복습"

    # -- 0: 설정 (오답 큐 표시) --------------------------------------------
    def _setup_page(self) -> QWidget:
        heading = QLabel("오답 우선 복습")
        font = heading.font()
        font.setPointSize(18)
        font.setBold(True)
        heading.setFont(font)

        self.queue_list = QListWidget()
        self.empty_label = QLabel("")
        self.empty_label.setWordWrap(True)
        self.num_box = QSpinBox()
        self.num_box.setRange(1, 50)
        self.num_box.setValue(5)
        self.start_btn = QPushButton("복습 시작")
        self.start_btn.clicked.connect(self._on_start_clicked)

        layout = QVBoxLayout()
        layout.addWidget(heading)
        layout.addWidget(QLabel("틀린 횟수가 많은 순"))
        layout.addWidget(self.queue_list, 1)
        layout.addWidget(self.empty_label)
        layout.addWidget(QLabel("문제 수"))
        layout.addWidget(self.num_box)
        layout.addWidget(self.start_btn)
        page = QWidget()
        page.setLayout(layout)
        self.refresh_setup()
        return page

    def refresh_setup(self) -> None:
        conn = self._conn()
        try:
            items = get_review_queue(conn, limit=20)
        finally:
            conn.close()
        self.queue_list.clear()
        for item in items:
            QListWidgetItem(
                f"{item.spelling} ({item.meaning_ko}) — "
                f"오답 {item.wrong_attempts}회 / 정답률 {item.accuracy:.0%}",
                self.queue_list,
            )
        self.empty_label.setText(
            "" if items else "오답 기록이 없습니다. 시작하면 전체 단어에서 무작위로 출제합니다."
        )

    def _on_start_clicked(self) -> None:
        self.start(num=self.num_box.value())

    def _build_questions(self, conn, tag: str, direction: str, num: int, seed):
        return build_review_quiz(conn, limit=num, seed=seed)
