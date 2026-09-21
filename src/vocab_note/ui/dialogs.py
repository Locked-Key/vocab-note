"""입력 다이얼로그. 검증(빈 값 거부)만 하고 저장은 호출자(MainWindow)가 합니다."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class WordDialog(QDialog):
    """단어 + 첫 뜻 + 태그 입력."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단어 추가")
        self.spelling = QLineEdit()
        self.spelling.setPlaceholderText("apple")
        self.pos = QLineEdit()
        self.pos.setPlaceholderText("noun")
        self.meaning = QLineEdit()
        self.meaning.setPlaceholderText("사과")
        self.ex_en = QLineEdit()
        self.ex_ko = QLineEdit()
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("과일, 토익 (쉼표 구분)")

        form = QFormLayout()
        form.addRow("영어*", self.spelling)
        form.addRow("품사", self.pos)
        form.addRow("뜻*", self.meaning)
        form.addRow("예문(EN)", self.ex_en)
        form.addRow("예문(KO)", self.ex_ko)
        form.addRow("태그", self.tags)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _on_ok(self) -> None:
        if not self.spelling.text().strip() or not self.meaning.text().strip():
            QMessageBox.warning(self, "입력 오류", "영어와 뜻은 필수입니다.")
            return
        self.accept()

    def data(self) -> dict:
        tags = [t.strip() for t in self.tags.text().split(",") if t.strip()]
        return {
            "spelling": self.spelling.text().strip(),
            "pos": self.pos.text().strip(),
            "meaning": self.meaning.text().strip(),
            "ex_en": self.ex_en.text().strip(),
            "ex_ko": self.ex_ko.text().strip(),
            "tags": tags,
        }


class SenseDialog(QDialog):
    """뜻 추가·수정 (동음이의어)."""

    def __init__(self, parent=None, initial: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("뜻 수정" if initial else "뜻 추가")
        initial = initial or {}
        self.pos = QLineEdit(initial.get("part_of_speech", ""))
        self.meaning = QLineEdit(initial.get("meaning_ko", ""))
        self.ex_en = QLineEdit(initial.get("example_en", ""))
        self.ex_ko = QLineEdit(initial.get("example_ko", ""))

        form = QFormLayout()
        form.addRow("품사", self.pos)
        form.addRow("뜻*", self.meaning)
        form.addRow("예문(EN)", self.ex_en)
        form.addRow("예문(KO)", self.ex_ko)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _on_ok(self) -> None:
        if not self.meaning.text().strip():
            QMessageBox.warning(self, "입력 오류", "뜻은 필수입니다.")
            return
        self.accept()

    def data(self) -> dict:
        return {
            "part_of_speech": self.pos.text().strip(),
            "meaning_ko": self.meaning.text().strip(),
            "example_en": self.ex_en.text().strip(),
            "example_ko": self.ex_ko.text().strip(),
        }
