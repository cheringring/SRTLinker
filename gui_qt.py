"""SRTLinker - PySide6 모던 GUI."""
from __future__ import annotations
import os
import sys
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from PySide6.QtCore import Qt, QThread, Signal, QObject, QSize
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QDragEnterEvent, QDropEvent, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QListWidget, QListWidgetItem,
    QProgressBar, QPlainTextEdit, QFileDialog, QMessageBox, QFrame, QSizePolicy,
    QStyle,
)

from pipeline import process_file, PipelineConfig


SUPPORTED_EXTS = {".srt", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv",
                  ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"}


# ====================== 스타일시트 (다크 테마) ======================
DARK_QSS = """
* { font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; font-size: 10pt; }

QMainWindow, QWidget { background: #1e1f26; color: #e6e7ea; }

QFrame#card {
    background: #262832;
    border: 1px solid #353846;
    border-radius: 12px;
}

QLabel#title { font-size: 18pt; font-weight: 600; color: #f5f6f8; }
QLabel#subtitle { color: #8a8e9c; font-size: 9pt; }
QLabel#sectionTitle { font-size: 10pt; font-weight: 600; color: #c8cad3; padding: 2px 0; }
QLabel#fieldLabel { color: #9ea3b3; font-size: 9pt; }

QLineEdit {
    background: #1a1c24;
    border: 1px solid #3a3d4d;
    border-radius: 6px;
    padding: 7px 10px;
    color: #e6e7ea;
    selection-background-color: #5b6cff;
}
QLineEdit:focus { border: 1px solid #6b7bff; }

QPushButton {
    background: #353846;
    border: 1px solid #41455a;
    border-radius: 6px;
    padding: 7px 14px;
    color: #e6e7ea;
}
QPushButton:hover { background: #3f4356; border: 1px solid #5765ff; }
QPushButton:pressed { background: #2c2f3c; }
QPushButton:disabled { background: #2a2c36; color: #5a5e6c; border: 1px solid #2f3240; }

QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5b6cff, stop:1 #7d4ee8);
    border: none;
    color: white;
    font-weight: 600;
    padding: 9px 22px;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6b7bff, stop:1 #8d5ef8);
}
QPushButton#primary:disabled { background: #3a3d4d; color: #6a6e7c; }

QCheckBox { color: #c8cad3; spacing: 8px; padding: 2px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 4px;
    border: 1px solid #4a4e60;
    background: #1a1c24;
}
QCheckBox::indicator:checked {
    background: #5b6cff;
    border: 1px solid #5b6cff;
    image: none;
}

QListWidget {
    background: #1a1c24;
    border: 1px solid #353846;
    border-radius: 8px;
    padding: 4px;
    color: #d6d8e0;
}
QListWidget::item { padding: 6px 8px; border-radius: 4px; }
QListWidget::item:selected { background: #3a4a8a; color: white; }
QListWidget::item:hover { background: #2a2d3a; }

QPlainTextEdit {
    background: #14151b;
    border: 1px solid #2a2c36;
    border-radius: 8px;
    color: #c8cad3;
    padding: 8px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 9pt;
}

QProgressBar {
    background: #14151b;
    border: 1px solid #2a2c36;
    border-radius: 10px;
    min-height: 22px;
    max-height: 22px;
    text-align: center;
    color: #c8cad3;
    font-size: 9pt;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5b6cff, stop:1 #7d4ee8);
    border-radius: 9px;
    margin: 0px;
}

QFrame#dropZone {
    background: #1a1c24;
    border: 2px dashed #3a3d4d;
    border-radius: 10px;
}
QFrame#dropZone[active="true"] {
    background: #20243a;
    border: 2px dashed #5b6cff;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3a3d4d; border-radius: 5px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #4a4e60; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


# ====================== Worker (백그라운드 번역) ======================
class TranslateWorker(QObject):
    log = Signal(str)
    progress = Signal(float, str)
    finished = Signal(list)  # list of error strings

    def __init__(self, files: list[Path], cfg: PipelineConfig):
        super().__init__()
        self.files = files
        self.cfg = cfg

    def run(self):
        errors: list[str] = []
        total = len(self.files)
        for idx, src in enumerate(self.files, 1):
            self.log.emit(f"[{idx}/{total}] {src.name} 처리 시작")

            def prog(msg: str, p: float, _i=idx):
                overall = ((_i - 1) + p) / total
                self.progress.emit(overall, f"({_i}/{total}) {msg}")

            try:
                out = process_file(src, self.cfg, progress=prog)
                self.log.emit(f"  → 저장: {out}")
            except Exception as e:
                tb = traceback.format_exc()
                err = f"{src.name}: {type(e).__name__}: {e}"
                errors.append(err)
                self.log.emit(f"  ✗ 실패: {err}")
                self.log.emit(tb)
        self.progress.emit(1.0, "전체 완료")
        self.finished.emit(errors)


# ====================== 드롭존 위젯 ======================
class DropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 22, 20, 22)
        layout.setSpacing(0)
        text = QLabel("여기로 파일을 드래그하거나 아래 '파일 추가' 버튼을 누르세요")
        text.setAlignment(Qt.AlignCenter)
        text.setWordWrap(True)
        text.setStyleSheet("color: #9ea3b3; font-size: 10pt; background: transparent; border: none; padding: 0;")
        layout.addWidget(text)

    def _set_active(self, active: bool):
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event):
        self._set_active(False)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
        self.files_dropped.emit(paths)
        self._set_active(False)


# ====================== 메인 윈도우 ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRTLinker — 비디오/자막 자동 번역기")
        self.resize(1040, 1020)
        self.setMinimumSize(780, 980)

        self.files: list[Path] = []
        self.thread: QThread | None = None
        self.worker: TranslateWorker | None = None

        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        self.log_file = logs_dir / f"srtlinker_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"

        self._build_ui()
        self._log("SRTLinker 준비 완료.")
        if not os.environ.get("OPENAI_API_KEY"):
            self._log("[경고] OPENAI_API_KEY 미설정. .env 또는 환경변수를 확인하세요.")

    # ---------------- UI ----------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        # 헤더
        header = QVBoxLayout()
        title = QLabel("SRTLinker")
        title.setObjectName("title")
        subtitle = QLabel("드래그앤드롭으로 비디오/오디오/자막을 자동 번역")
        subtitle.setObjectName("subtitle")
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        # 설정 카드
        settings_card = self._make_card()
        settings_card.setFixedHeight(220)
        scl = QVBoxLayout(settings_card)
        scl.setContentsMargins(16, 14, 16, 14)
        scl.setSpacing(10)

        sec = QLabel("설정")
        sec.setObjectName("sectionTitle")
        scl.addWidget(sec)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.lang_input = QLineEdit("Korean")
        self.src_lang_input = QLineEdit("en")
        self.model_input = QLineEdit(os.environ.get("OPENAI_MODEL", "gpt-4o"))
        self.stt_input = QLineEdit("whisper-1")
        self.out_input = QLineEdit(str(Path("output").resolve()))
        browse_btn = QPushButton("찾기")
        browse_btn.clicked.connect(self._pick_out)

        grid.addWidget(self._field_label("번역 언어", center=True), 0, 0)
        grid.addWidget(self.lang_input, 0, 1)
        grid.addWidget(self._field_label("원본 언어 (선택)", center=True), 0, 2)
        grid.addWidget(self.src_lang_input, 0, 3)
        grid.addWidget(self._field_label("번역 모델", center=True), 1, 0)
        grid.addWidget(self.model_input, 1, 1)
        grid.addWidget(self._field_label("전사 모델", center=True), 1, 2)
        grid.addWidget(self.stt_input, 1, 3)
        grid.addWidget(self._field_label("출력 폴더", center=True), 2, 0)
        grid.addWidget(self.out_input, 2, 1, 1, 2)
        grid.addWidget(browse_btn, 2, 3)
        # 입력칸 컴럼을 동일 비율로 확장
        grid.setColumnMinimumWidth(0, 100)
        grid.setColumnMinimumWidth(2, 100)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        scl.addLayout(grid)

        self.merge_check = QCheckBox("문장인식 분할 번역 (추천)")
        self.merge_check.setChecked(True)
        scl.addWidget(self.merge_check)

        root.addWidget(settings_card)

        # 파일 카드
        file_card = self._make_card()
        file_card.setFixedHeight(350)
        fcl = QVBoxLayout(file_card)
        fcl.setContentsMargins(24, 18, 24, 22)
        fcl.setSpacing(16)

        sec2 = QLabel("파일")
        sec2.setObjectName("sectionTitle")
        fcl.addWidget(sec2)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._add_files)
        fcl.addWidget(self.drop_zone)

        self.file_list = QListWidget()
        self.file_list.setFixedHeight(120)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        fcl.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        add_btn = QPushButton("파일 추가")
        rm_btn = QPushButton("선택 제거")
        clear_btn = QPushButton("모두 지우기")
        add_btn.clicked.connect(self._pick_files)
        rm_btn.clicked.connect(self._remove_selected)
        clear_btn.clicked.connect(self._clear_files)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        fcl.addLayout(btn_row)

        root.addWidget(file_card)

        # 진행률 + 액션 (단일 행으로 압축해 번역 시작 버튼을 항상 노출)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFormat("대기 중")
        self.progress.setFixedHeight(22)
        root.addWidget(self.progress)

        action_row = QHBoxLayout()
        self.status_label = QLabel("대기 중")
        self.status_label.setStyleSheet("color: #9ea3b3;")
        action_row.addWidget(self.status_label)
        action_row.addStretch(1)
        log_btn = QPushButton("로그 파일")
        out_btn = QPushButton("출력 폴더")
        log_btn.clicked.connect(self._open_log)
        out_btn.clicked.connect(self._open_output)
        self.run_btn = QPushButton("번역 시작")
        self.run_btn.setObjectName("primary")
        self.run_btn.setFixedHeight(40)
        self.run_btn.setMinimumWidth(160)
        self.run_btn.clicked.connect(self._start)
        action_row.addWidget(log_btn)
        action_row.addWidget(out_btn)
        action_row.addWidget(self.run_btn)
        root.addLayout(action_row)

        # 로그
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(130)
        root.addWidget(self.log_view)

        # 창을 늘려도 위 요소들은 고정 — 여분은 아래 빈 공간으로
        root.addStretch(1)

    def _make_card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("card")
        return f

    def _field_label(self, text: str, center: bool = False) -> QLabel:
        lb = QLabel(text)
        lb.setObjectName("fieldLabel")
        if center:
            lb.setAlignment(Qt.AlignCenter)
        return lb

    # ---------------- 파일 처리 ----------------
    def _pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "자막/비디오 선택", "",
            "미디어 (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.m4a *.srt);;모든 파일 (*.*)",
        )
        self._add_files([Path(p) for p in paths])

    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "출력 폴더 선택", self.out_input.text())
        if d:
            self.out_input.setText(d)

    def _add_files(self, paths: list[Path]):
        added = 0
        for p in paths:
            if not p.exists():
                continue
            if p.suffix.lower() not in SUPPORTED_EXTS:
                self._log(f"[무시] 지원 안함: {p.name}")
                continue
            if p in self.files:
                continue
            self.files.append(p)
            self.file_list.addItem(QListWidgetItem(str(p)))
            added += 1
        if added:
            self._log(f"{added}개 파일 추가됨 (총 {len(self.files)}개)")

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            del self.files[row]

    def _clear_files(self):
        self.file_list.clear()
        self.files.clear()

    # ---------------- 실행 ----------------
    def _start(self):
        if self.thread and self.thread.isRunning():
            return
        if not self.files:
            self._log("파일을 먼저 추가하세요.")
            return
        if not os.environ.get("OPENAI_API_KEY"):
            QMessageBox.warning(self, "API 키 누락", "OPENAI_API_KEY가 설정되어 있지 않습니다.\n.env 파일 또는 환경변수를 확인하세요.")
            return

        cfg = PipelineConfig(
            model_translate=self.model_input.text().strip() or "gpt-4o",
            model_transcribe=self.stt_input.text().strip() or "whisper-1",
            target_lang=self.lang_input.text().strip() or "Korean",
            source_lang=(self.src_lang_input.text().strip() or None),
            output_dir=Path(self.out_input.text().strip() or "output"),
            glossary_path=Path("glossary.json") if Path("glossary.json").exists() else None,
            sentence_aware=self.merge_check.isChecked(),
        )

        self.run_btn.setEnabled(False)
        self.progress.setValue(0)

        self.thread = QThread(self)
        self.worker = TranslateWorker(list(self.files), cfg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _on_progress(self, p: float, msg: str):
        self.progress.setValue(int(p * 1000))
        self.progress.setFormat(f"{int(p*100)}%  {msg}")
        self.status_label.setText(msg)

    def _on_finished(self, errors: list):
        self.run_btn.setEnabled(True)
        if errors:
            self._log(f"⚠ {len(errors)}개 파일 실패. 상세는 로그 파일 참고: {self.log_file}")
            QMessageBox.critical(self, "실패", "다음 파일에서 오류 발생:\n\n" + "\n".join(errors))
        else:
            self._log("모든 작업 완료.")

    # ---------------- 로그 ----------------
    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_view.appendPlainText(line)
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _open_output(self):
        path = Path(self.out_input.text().strip() or "output")
        path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def _open_log(self):
        if self.log_file.exists():
            self._open_path(self.log_file)
        else:
            QMessageBox.information(self, "로그", "아직 로그 파일이 없습니다.")

    def _open_path(self, path: Path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            QMessageBox.warning(self, "열기 실패", str(e))


def main():
    load_dotenv()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
