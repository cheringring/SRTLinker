"""SRTLinker GUI - \ub4dc\ub798\uadf8&\ub4dc\ub86d\uc73c\ub85c \ube44\ub514\uc624/SRT \uc790\ub3d9 \ubc88\uc5ed."""
from __future__ import annotations
import os
import queue
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, StringVar, BooleanVar, END
import tkinter as tk

from dotenv import load_dotenv

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except Exception:
    TkinterDnD = None
    DND_FILES = None
    DND_AVAILABLE = False

from pipeline import process_file, PipelineConfig


SUPPORTED_EXTS = {".srt", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv",
                  ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"}


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("SRTLinker - \ube44\ub514\uc624/\uc790\ub9c9 \uc790\ub3d9 \ubc88\uc5ed\uae30")
        root.geometry("720x560")
        root.minsize(640, 520)

        self.files: list[Path] = []
        self.msg_q: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_errors: list[str] = []

        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        self.log_file = logs_dir / f"srtlinker_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"

        self._build_ui()
        self.root.after(100, self._drain_queue)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # \uc0c1\ub2e8 \uc124\uc815
        top = ttk.LabelFrame(self.root, text="\uc124\uc815")
        top.pack(fill="x", **pad)

        ttk.Label(top, text="\ubc88\uc5ed \uc5b8\uc5b4").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.lang_var = StringVar(value="Korean")
        ttk.Entry(top, textvariable=self.lang_var, width=14).grid(row=0, column=1, sticky="w")

        ttk.Label(top, text="\uc6d0\ubcf8 \uc5b8\uc5b4(\uc120\ud0dd)").grid(row=0, column=2, sticky="w", padx=(16, 6))
        self.src_lang_var = StringVar(value="en")
        ttk.Entry(top, textvariable=self.src_lang_var, width=8).grid(row=0, column=3, sticky="w")

        ttk.Label(top, text="\ubc88\uc5ed \ubaa8\ub378").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.model_var = StringVar(value=os.environ.get("OPENAI_MODEL", "gpt-4o"))
        ttk.Entry(top, textvariable=self.model_var, width=20).grid(row=1, column=1, sticky="w")

        ttk.Label(top, text="\uc804\uc0ac \ubaa8\ub378").grid(row=1, column=2, sticky="w", padx=(16, 6))
        self.stt_var = StringVar(value="whisper-1")
        ttk.Entry(top, textvariable=self.stt_var, width=20).grid(row=1, column=3, sticky="w")

        ttk.Label(top, text="\ucd9c\ub825 \ud3f4\ub354").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.out_var = StringVar(value=str(Path("output").resolve()))
        ttk.Entry(top, textvariable=self.out_var, width=50).grid(row=2, column=1, columnspan=2, sticky="we")
        ttk.Button(top, text="\ucc3e\uae30", command=self._pick_out).grid(row=2, column=3, sticky="w")
        top.columnconfigure(1, weight=1)

        self.merge_var = BooleanVar(value=True)
        ttk.Checkbutton(
            top,
            text="\ubb38\uc7a5\uc778\uc2dd \ubd84\ud560 \ubc88\uc5ed (1:1 \uad6c\uc870 \uc720\uc9c0 + \uc790\uc5f0\uc2a4\ub7ec\uc6c0 \ucd94\uad8c)",
            variable=self.merge_var,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=(2, 4))

        # \ub4dc\ub86d \uc601\uc5ed
        drop_frame = ttk.LabelFrame(self.root, text="\ud30c\uc77c \ub4dc\ub86d (\ube44\ub514\uc624 / \uc624\ub514\uc624 / .srt)")
        drop_frame.pack(fill="both", expand=True, **pad)

        self.drop_label = tk.Label(
            drop_frame,
            text=("\uc5ec\uae30\ub85c \ud30c\uc77c\uc744 \ub4dc\ub798\uadf8 \ud558\uac70\ub098 \uc544\ub798 '\ud30c\uc77c \ucd94\uac00' \ubc84\ud2bc\uc744 \ub204\ub974\uc138\uc694.\n"
                  "(.mp4, .mkv, .mov, .mp3, .srt ...)"
                  if DND_AVAILABLE else
                  "'\ud30c\uc77c \ucd94\uac00' \ubc84\ud2bc\uc73c\ub85c \ud30c\uc77c\uc744 \uc120\ud0dd\ud558\uc138\uc694.\n(tkinterdnd2 \ubbf8\uc124\uce58 \u2192 \ub4dc\ub798\uadf8\uc564\ub4dc\ub86d \ube44\ud65c\uc131)"),
            bg="#f4f6fb", relief="groove", bd=2, fg="#555", height=6,
        )
        self.drop_label.pack(fill="x", padx=8, pady=8)
        if DND_AVAILABLE:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop)

        # \ud30c\uc77c \ubaa9\ub85d
        list_row = ttk.Frame(drop_frame)
        list_row.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.listbox = tk.Listbox(list_row, height=8)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_row, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(drop_frame)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="\ud30c\uc77c \ucd94\uac00", command=self._pick_files).pack(side="left")
        ttk.Button(btns, text="\uc120\ud0dd \uc81c\uac70", command=self._remove_selected).pack(side="left", padx=6)
        ttk.Button(btns, text="\ubaa8\ub450 \uc9c0\uc6b0\uae30", command=self._clear).pack(side="left")

        # \uc9c4\ud589/\ub85c\uadf8
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=1.0)
        self.progress.pack(fill="x", side="top")
        self.status_var = StringVar(value="\ub300\uae30 \uc911")
        ttk.Label(bottom, textvariable=self.status_var).pack(anchor="w", pady=(4, 0))

        action = ttk.Frame(self.root)
        action.pack(fill="x", **pad)
        self.run_btn = ttk.Button(action, text="\ubc88\uc5ed \uc2dc\uc791", command=self._start)
        self.run_btn.pack(side="right")
        ttk.Button(action, text="\ucd9c\ub825 \ud3f4\ub354 \uc5f4\uae30", command=self._open_output).pack(side="right", padx=6)
        ttk.Button(action, text="\ub85c\uadf8 \ud30c\uc77c \uc5f4\uae30", command=self._open_log).pack(side="right")

        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log = tk.Text(log_frame, height=14, bg="#111", fg="#e6e6e6", insertbackground="#fff", wrap="word")
        self.log.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        log_scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=log_scroll.set)
        self._log("SRTLinker \uc900\ube44 \uc644\ub8cc.")
        if not os.environ.get("OPENAI_API_KEY"):
            self._log("[\uacbd\uace0] OPENAI_API_KEY \ubbf8\uc124\uc815. .env \ub610\ub294 \ud658\uacbd\ubcc0\uc218\ub97c \ud655\uc778\ud558\uc138\uc694.")

    # ---------- \uc774\ubca4\ud2b8 ----------
    def _on_drop(self, event):
        paths = self._parse_drop(event.data)
        self._add_files(paths)

    def _parse_drop(self, data: str) -> list[Path]:
        # tkdnd\ub294 \uacf5\ubc31\ud3ec\ud568 \uacbd\ub85c\ub97c {}\ub85c \uac10\uc2f8\uc11c \uc804\ub2ec
        result = []
        buf = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                buf = ""
            elif ch == "}":
                in_brace = False
                if buf:
                    result.append(buf); buf = ""
            elif ch == " " and not in_brace:
                if buf:
                    result.append(buf); buf = ""
            else:
                buf += ch
        if buf:
            result.append(buf)
        return [Path(p) for p in result]

    def _pick_files(self):
        paths = filedialog.askopenfilenames(
            title="\uc790\ub9c9/\ube44\ub514\uc624 \uc120\ud0dd",
            filetypes=[
                ("\ubbf8\ub514\uc5b4", "*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.m4a *.srt"),
                ("\ubaa8\ub4e0 \ud30c\uc77c", "*.*"),
            ],
        )
        self._add_files([Path(p) for p in paths])

    def _pick_out(self):
        d = filedialog.askdirectory(title="\ucd9c\ub825 \ud3f4\ub354 \uc120\ud0dd")
        if d:
            self.out_var.set(d)

    def _add_files(self, paths: list[Path]):
        for p in paths:
            if not p.exists():
                continue
            if p.suffix.lower() not in SUPPORTED_EXTS:
                self._log(f"[\ubb34\uc2dc] \uc9c0\uc6d0 \uc548\ud568: {p.name}")
                continue
            if p in self.files:
                continue
            self.files.append(p)
            self.listbox.insert(END, str(p))

    def _remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.files[i]

    def _clear(self):
        self.listbox.delete(0, END)
        self.files.clear()

    # ---------- \uc2e4\ud589 ----------
    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.files:
            self._log("\ud30c\uc77c\uc744 \uba3c\uc800 \ucd94\uac00\ud558\uc138\uc694.")
            return
        if not os.environ.get("OPENAI_API_KEY"):
            self._log("[\uc911\ub2e8] OPENAI_API_KEY \uac00 \uc5c6\uc2b5\ub2c8\ub2e4.")
            return

        cfg = PipelineConfig(
            model_translate=self.model_var.get().strip() or "gpt-4o",
            model_transcribe=self.stt_var.get().strip() or "whisper-1",
            target_lang=self.lang_var.get().strip() or "Korean",
            source_lang=(self.src_lang_var.get().strip() or None),
            output_dir=Path(self.out_var.get().strip() or "output"),
            glossary_path=Path("glossary.json") if Path("glossary.json").exists() else None,
            sentence_aware=bool(self.merge_var.get()),
        )
        files = list(self.files)
        self.run_btn.configure(state="disabled")
        self.progress["value"] = 0
        self.worker = threading.Thread(target=self._run_worker, args=(files, cfg), daemon=True)
        self.worker.start()

    def _run_worker(self, files: list[Path], cfg: PipelineConfig):
        total = len(files)
        self.last_errors = []
        try:
            for idx, src in enumerate(files, 1):
                self._post("log", f"[{idx}/{total}] {src.name} \ucc98\ub9ac \uc2dc\uc791")
                def prog(msg: str, p: float, _i=idx):
                    overall = ((_i - 1) + p) / total
                    self._post("progress", (overall, f"({_i}/{total}) {msg}"))
                try:
                    out = process_file(src, cfg, progress=prog)
                    self._post("log", f"  \u2192 \uc800\uc7a5: {out}")
                except Exception as e:
                    tb = traceback.format_exc()
                    err_summary = f"{src.name}: {type(e).__name__}: {e}"
                    self.last_errors.append(err_summary)
                    self._post("log", f"  \u2717 \uc2e4\ud328: {err_summary}")
                    self._post("log", tb)
            self._post("progress", (1.0, "\uc804\uccb4 \uc644\ub8cc"))
            if self.last_errors:
                self._post("log", f"\u26a0 {len(self.last_errors)}\uac1c \ud30c\uc77c \uc2e4\ud328. \uc0c1\uc138\ub294 \ub85c\uadf8 \ud30c\uc77c \ucc38\uace0: {self.log_file}")
                self._post("error_popup", "\n".join(self.last_errors))
            else:
                self._post("log", "\ubaa8\ub4e0 \uc791\uc5c5 \uc644\ub8cc.")
        finally:
            self._post("done", None)

    # ---------- \uc2a4\ub808\ub4dc \uac04 \ud1b5\uc2e0 ----------
    def _post(self, kind: str, payload):
        self.msg_q.put((kind, payload))

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "progress":
                    p, msg = payload
                    self.progress["value"] = p
                    self.status_var.set(msg)
                elif kind == "error_popup":
                    messagebox.showerror("\uc2e4\ud328", f"\ub2e4\uc74c \ud30c\uc77c\uc5d0\uc11c \uc624\ub958 \ubc1c\uc0dd:\n\n{payload}\n\n\uc804\uccb4 \ud2b8\ub808\uc774\uc2a4\ubc31\uc740 \ub85c\uadf8 \ucc3d/\ud30c\uc77c \ucc38\uace0.")
                elif kind == "done":
                    self.run_btn.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _log(self, msg: str):
        self.log.insert(END, msg + "\n")
        self.log.see(END)
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
        except Exception:
            pass

    def _open_output(self):
        path = Path(self.out_var.get().strip() or "output")
        path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def _open_log(self):
        if self.log_file.exists():
            self._open_path(self.log_file)
        else:
            messagebox.showinfo("\ub85c\uadf8", "\uc544\uc9c1 \ub85c\uadf8 \ud30c\uc77c\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.")

    def _open_path(self, path: Path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showwarning("\uc5f4\uae30 \uc2e4\ud328", str(e))


def main():
    load_dotenv()
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
