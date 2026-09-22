"""메인 윈도우: 단어 목록 | 상세 화면.

규칙: 이 파일에는 SQL이 없습니다. 데이터 작업은 전부
vocab_service / tag_service 함수로만 수행합니다 (UI-로직 분리).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..db import get_connection
from ..tag_service import get_word_tags, list_tags, search_words, tag_word, untag_word
from ..vocab_service import (
    VocabError,
    add_sense,
    add_word,
    delete_sense,
    delete_word,
    find_duplicate,
    get_sense,
    get_word,
    update_sense,
)
from .dialogs import SenseDialog, WordDialog
from .quiz_dialog import QuizDialog
from .theme import apply_theme

ALL_TAGS = "전체 태그"


class MainWindow(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self._db_path = db_path
        self._dark = False
        self.setWindowTitle("영단어 학습 노트")
        self.resize(960, 620)
        self._build_ui()
        self.refresh_all()

    # -- UI 구성 -----------------------------------------------------
    def _build_ui(self) -> None:
        # 왼쪽: 검색 + 필터 + 목록
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색 (철자·뜻)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh_list())

        self.tag_filter = QComboBox()
        self.tag_filter.currentTextChanged.connect(lambda _: self.refresh_list())
        self.order = QComboBox()
        self.order.addItems(["alpha", "recent"])
        self.order.currentTextChanged.connect(lambda _: self.refresh_list())

        filter_row = QHBoxLayout()
        filter_row.addWidget(self.tag_filter, 2)
        filter_row.addWidget(QLabel("정렬"))
        filter_row.addWidget(self.order, 1)

        self.word_list = QListWidget()
        self.word_list.currentItemChanged.connect(lambda *_: self.show_detail())

        self.add_btn = QPushButton("+ 추가")
        self.add_btn.clicked.connect(self.on_add_word)
        self.del_btn = QPushButton("- 삭제")
        self.del_btn.clicked.connect(self.on_delete_word)
        list_btns = QHBoxLayout()
        list_btns.addWidget(self.add_btn)
        list_btns.addWidget(self.del_btn)

        left = QVBoxLayout()
        left.addWidget(self.search)
        left.addLayout(filter_row)
        left.addWidget(self.word_list, 1)
        left.addLayout(list_btns)
        left_widget = QWidget()
        left_widget.setLayout(left)

        # 오른쪽: 상세
        self.title = QLabel("(단어 선택)")
        font = self.title.font()
        font.setPointSize(20)
        font.setBold(True)
        self.title.setFont(font)
        self.tags_label = QLabel("")
        self.tags_label.setWordWrap(True)

        self.sense_list = QListWidget()
        self.sense_list.currentItemChanged.connect(lambda *_: self.show_sense_detail())
        self.sense_detail = QLabel("")
        self.sense_detail.setWordWrap(True)
        self.sense_detail.setAlignment(Qt.AlignTop)

        self.add_sense_btn = QPushButton("뜻 추가")
        self.add_sense_btn.clicked.connect(self.on_add_sense)
        self.edit_sense_btn = QPushButton("뜻 수정")
        self.edit_sense_btn.clicked.connect(self.on_edit_sense)
        self.del_sense_btn = QPushButton("뜻 삭제")
        self.del_sense_btn.clicked.connect(self.on_delete_sense)
        self.tag_btn = QPushButton("태그 붙이기")
        self.tag_btn.clicked.connect(self.on_tag_word)
        self.untag_btn = QPushButton("태그 떼기")
        self.untag_btn.clicked.connect(self.on_untag_word)
        sense_btns = QHBoxLayout()
        for b in (self.add_sense_btn, self.edit_sense_btn, self.del_sense_btn,
                  self.tag_btn, self.untag_btn):
            sense_btns.addWidget(b)

        right = QVBoxLayout()
        right.addWidget(self.title)
        right.addWidget(self.tags_label)
        right.addWidget(QLabel("뜻 목록"))
        right.addWidget(self.sense_list, 1)
        right.addWidget(self.sense_detail, 1)
        right.addLayout(sense_btns)
        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # 상단: 퀴즈 + 다크모드 토글
        self.quiz_btn = QPushButton("퀴즈")
        self.quiz_btn.clicked.connect(self.open_quiz)
        self.dark_toggle = QCheckBox("다크 모드")
        self.dark_toggle.toggled.connect(self.on_toggle_dark)
        top = QHBoxLayout()
        top.addStretch(1)
        top.addWidget(self.quiz_btn)
        top.addWidget(self.dark_toggle)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addWidget(splitter, 1)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

    # -- 데이터 접근 (서비스 함수만 사용) -------------------------------
    def _conn(self):
        return get_connection(self._db_path)

    def _current_word_id(self) -> int | None:
        item = self.word_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _current_sense_id(self) -> int | None:
        item = self.sense_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    # -- 새로고침 -------------------------------------------------------
    def refresh_all(self) -> None:
        self.refresh_tag_filter()
        self.refresh_list()

    def refresh_tag_filter(self) -> None:
        prev = self.tag_filter.currentText()
        conn = self._conn()
        try:
            names = [t.name for t, _ in list_tags(conn)]
        finally:
            conn.close()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem(ALL_TAGS)
        self.tag_filter.addItems(sorted(names))
        if prev in names or prev == ALL_TAGS:
            self.tag_filter.setCurrentText(prev)
        self.tag_filter.blockSignals(False)

    def refresh_list(self) -> None:
        conn = self._conn()
        try:
            tag = self.tag_filter.currentText()
            words = search_words(
                conn,
                query=self.search.text(),
                tag="" if tag == ALL_TAGS else tag,
                order=self.order.currentText(),
            )
        except VocabError as e:
            QMessageBox.warning(self, "조회 오류", str(e))
            return
        finally:
            conn.close()
        prev_id = self._current_word_id()
        self.word_list.blockSignals(True)
        self.word_list.clear()
        for w in words:
            meanings = "; ".join(
                f"({s.part_of_speech}) {s.meaning_ko}" if s.part_of_speech else s.meaning_ko
                for s in w.senses
            ) or "(뜻 없음)"
            tags = f"  #{' #'.join(t.name for t in w.tags)}" if w.tags else ""
            item = QListWidgetItem(f"{w.spelling} — {meanings}{tags}")
            item.setData(Qt.UserRole, w.id)
            self.word_list.addItem(item)
            if w.id == prev_id:
                self.word_list.setCurrentItem(item)
        self.word_list.blockSignals(False)
        self.show_detail()

    def show_detail(self) -> None:
        word_id = self._current_word_id()
        if word_id is None:
            self.title.setText("(단어 선택)")
            self.tags_label.setText("")
            self.sense_list.clear()
            self.sense_detail.setText("")
            return
        conn = self._conn()
        try:
            word = get_word(conn, word_id)
            tags = get_word_tags(conn, word_id)
        except VocabError as e:
            QMessageBox.warning(self, "조회 오류", str(e))
            return
        finally:
            conn.close()
        self.title.setText(word.spelling)
        self.tags_label.setText(
            "태그: " + ", ".join(f"#{t.name}" for t in tags) if tags else "태그 없음"
        )
        self.sense_list.blockSignals(True)
        self.sense_list.clear()
        for s in word.senses:
            pos = f"({s.part_of_speech}) " if s.part_of_speech else ""
            item = QListWidgetItem(f"{pos}{s.meaning_ko}")
            item.setData(Qt.UserRole, s.id)
            self.sense_list.addItem(item)
        if word.senses:
            self.sense_list.setCurrentRow(0)
        self.sense_list.blockSignals(False)
        self.show_sense_detail()

    def show_sense_detail(self) -> None:
        sense_id = self._current_sense_id()
        if sense_id is None:
            self.sense_detail.setText("")
            return
        conn = self._conn()
        try:
            s = get_sense(conn, sense_id)
        except VocabError as e:
            QMessageBox.warning(self, "조회 오류", str(e))
            return
        finally:
            conn.close()
        lines = [s.meaning_ko]
        if s.example_en:
            lines += ["", f"예문: {s.example_en}"]
        if s.example_ko:
            lines.append(s.example_ko)
        self.sense_detail.setText("\n".join(lines))

    # -- 액션 ------------------------------------------------------------
    def on_add_word(self) -> None:
        dlg = WordDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        conn = self._conn()
        try:
            dup = find_duplicate(conn, d["spelling"])
            if dup is not None:  # 2단계 중복 흐름을 GUI로 재현
                ans = QMessageBox.question(
                    self, "중복 경고",
                    f"'{d['spelling']}'은(는) 이미 있습니다.\n기존 단어에 다른 뜻으로 추가할까요?",
                )
                if ans != QMessageBox.Yes:
                    return
                add_sense(conn, dup.id, d["pos"], d["meaning"], d["ex_en"], d["ex_ko"])
                for name in d["tags"]:
                    tag_word(conn, dup.id, name)
                target = dup.id
            else:
                word = add_word(conn, d["spelling"])
                add_sense(conn, word.id, d["pos"], d["meaning"], d["ex_en"], d["ex_ko"])
                for name in d["tags"]:
                    tag_word(conn, word.id, name)
                target = word.id
        except VocabError as e:
            QMessageBox.warning(self, "저장 오류", str(e))
            return
        finally:
            conn.close()
        self.refresh_all()
        self._select_word(target)

    def _select_word(self, word_id: int) -> None:
        for i in range(self.word_list.count()):
            if self.word_list.item(i).data(Qt.UserRole) == word_id:
                self.word_list.setCurrentRow(i)
                return

    def on_delete_word(self) -> None:
        word_id = self._current_word_id()
        if word_id is None:
            return
        conn = self._conn()
        try:
            word = get_word(conn, word_id)
        finally:
            conn.close()
        ans = QMessageBox.question(
            self, "삭제 확인", f"[{word.spelling}] + 뜻 {len(word.senses)}개를 삭제할까요?"
        )
        if ans != QMessageBox.Yes:
            return
        conn = self._conn()
        try:
            delete_word(conn, word_id)
        except VocabError as e:
            QMessageBox.warning(self, "삭제 오류", str(e))
            return
        finally:
            conn.close()
        self.refresh_all()

    def on_add_sense(self) -> None:
        word_id = self._current_word_id()
        if word_id is None:
            QMessageBox.information(self, "안내", "먼저 단어를 선택하세요.")
            return
        dlg = SenseDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        conn = self._conn()
        try:
            add_sense(conn, word_id, d["part_of_speech"], d["meaning_ko"],
                      d["example_en"], d["example_ko"])
        except VocabError as e:
            QMessageBox.warning(self, "저장 오류", str(e))
            return
        finally:
            conn.close()
        self.refresh_all()

    def on_edit_sense(self) -> None:
        sense_id = self._current_sense_id()
        if sense_id is None:
            return
        conn = self._conn()
        try:
            s = get_sense(conn, sense_id)
        finally:
            conn.close()
        dlg = SenseDialog(self, initial={
            "part_of_speech": s.part_of_speech, "meaning_ko": s.meaning_ko,
            "example_en": s.example_en, "example_ko": s.example_ko,
        })
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.data()
        conn = self._conn()
        try:
            update_sense(conn, sense_id, part_of_speech=d["part_of_speech"],
                         meaning_ko=d["meaning_ko"], example_en=d["example_en"],
                         example_ko=d["example_ko"])
        except VocabError as e:
            QMessageBox.warning(self, "수정 오류", str(e))
            return
        finally:
            conn.close()
        self.refresh_all()

    def on_delete_sense(self) -> None:
        sense_id = self._current_sense_id()
        if sense_id is None:
            return
        ans = QMessageBox.question(self, "삭제 확인", "이 뜻을 삭제할까요?")
        if ans != QMessageBox.Yes:
            return
        conn = self._conn()
        try:
            delete_sense(conn, sense_id)
        except VocabError as e:
            QMessageBox.warning(self, "삭제 오류", str(e))
            return
        finally:
            conn.close()
        self.refresh_all()

    def on_tag_word(self) -> None:
        word_id = self._current_word_id()
        if word_id is None:
            return
        name, ok = QInputDialog.getText(self, "태그 붙이기", "태그명:")
        if not ok or not name.strip():
            return
        conn = self._conn()
        try:
            tag_word(conn, word_id, name)
        except VocabError as e:
            QMessageBox.warning(self, "태그 오류", str(e))
            return
        finally:
            conn.close()
        self.refresh_all()

    def on_untag_word(self) -> None:
        word_id = self._current_word_id()
        if word_id is None:
            return
        conn = self._conn()
        try:
            tags = get_word_tags(conn, word_id)
        finally:
            conn.close()
        if not tags:
            QMessageBox.information(self, "안내", "붙은 태그가 없습니다.")
            return
        name, ok = QInputDialog.getItem(
            self, "태그 떼기", "태그:", [t.name for t in tags], editable=False
        )
        if not ok:
            return
        conn = self._conn()
        try:
            untag_word(conn, word_id, name)
        except VocabError as e:
            QMessageBox.warning(self, "태그 오류", str(e))
            return
        finally:
            conn.close()
        self.refresh_all()

    def on_toggle_dark(self, checked: bool) -> None:
        self._dark = checked
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, checked)

    def open_quiz(self) -> None:
        QuizDialog(self, self._db_path).exec()
