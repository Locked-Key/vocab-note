"""학습 기록 본문 페이지: 정답률·일자별·오답 노트·최근 풀이.

읽기 전용 — stats_service 집계 함수만 호출합니다.
"""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...db import get_connection
from ...stats_service import (
    daily_stats,
    direction_stats,
    overall_stats,
    recent_attempts,
    wrong_notes,
)

DIRECTION_LABELS = {"en_to_ko": "영어→뜻", "ko_to_en": "뜻→영어"}


class StatsPage(QWidget):
    title_text = "학습 기록"

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self._db_path = db_path

        heading = QLabel("학습 기록")
        font = heading.font()
        font.setPointSize(18)
        font.setBold(True)
        heading.setFont(font)
        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.reset)
        top = QHBoxLayout()
        top.addWidget(heading)
        top.addStretch(1)
        top.addWidget(refresh_btn)

        self.overall_label = QLabel("")
        f = self.overall_label.font()
        f.setPointSize(15)
        self.overall_label.setFont(f)
        self.direction_label = QLabel("")

        self.daily_list = QListWidget()
        self.wrong_list = QListWidget()
        self.recent_list = QListWidget()

        columns = QHBoxLayout()
        for title, widget in (("일자별", self.daily_list),
                              ("오답 노트", self.wrong_list),
                              ("최근 풀이", self.recent_list)):
            col = QVBoxLayout()
            col.addWidget(QLabel(title))
            col.addWidget(widget, 1)
            box = QWidget()
            box.setLayout(col)
            columns.addWidget(box, 1)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.overall_label)
        layout.addWidget(self.direction_label)
        layout.addLayout(columns, 1)
        self.setLayout(layout)
        self.reset()

    def _conn(self):
        return get_connection(self._db_path)

    def reset(self) -> None:
        """페이지 진입/새로고침 시 집계를 다시 읽습니다."""
        conn = self._conn()
        try:
            overall = overall_stats(conn)
            directions = direction_stats(conn)
            days = daily_stats(conn, 7)
            wrongs = wrong_notes(conn, 10)
            recents = recent_attempts(conn, 10)
        finally:
            conn.close()

        self.overall_label.setText(
            f"전체 정답률: {overall.correct}/{overall.total} ({overall.accuracy:.0%})"
            if overall.total else "아직 푼 문제가 없습니다."
        )
        self.direction_label.setText("  |  ".join(
            f"{DIRECTION_LABELS.get(d.direction, d.direction)}: "
            f"{d.correct}/{d.total} ({d.accuracy:.0%})" for d in directions
        ))

        self.daily_list.clear()
        for d in days:
            QListWidgetItem(f"{d.day}  {d.correct}/{d.total} ({d.accuracy:.0%})",
                            self.daily_list)
        if not days:
            QListWidgetItem("(기록 없음)", self.daily_list)

        self.wrong_list.clear()
        for s in wrongs:
            QListWidgetItem(
                f"{s.spelling} ({s.meaning_ko}) — 오답 {s.wrong}회 / {s.accuracy:.0%}",
                self.wrong_list)
        if not wrongs:
            QListWidgetItem("(오답 없음)", self.wrong_list)

        self.recent_list.clear()
        for r in recents:
            mark = "O" if r.is_correct else "X"
            QListWidgetItem(f"[{mark}] {r.spelling} ({r.meaning_ko})  {r.answered_at}",
                            self.recent_list)
        if not recents:
            QListWidgetItem("(기록 없음)", self.recent_list)
