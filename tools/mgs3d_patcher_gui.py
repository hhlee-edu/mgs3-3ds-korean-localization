#!/usr/bin/env python3
"""Small Windows GUI over the existing MGS3D patcher CLI."""
from __future__ import annotations

import argparse
import contextlib
import io
import queue
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD

import mgs3d_patcher as patcher

TITLE = "MGS3D KOR Patcher v0.94a1"
LUMA_WARNING = (
    "Luma game patching이나 /luma/titles/0004000000081E00/ 잔재가 있으면 "
    "이중 패치로 실행 문제가 생길 수 있습니다."
)
WAIT_NOTICE = "빌드는 몇 분 정도 걸릴 수 있습니다. 완료될 때까지 창을 닫지 말고 기다려 주세요."


def short_reason(report: patcher.Report) -> str:
    text = " ".join(report.reasons)
    if "encrypted" in text:
        return "암호화된 파일입니다. 복호화된 clean USA 1.0 CCI/3DS가 필요합니다."
    if "title ID" in text or "product code" in text:
        return "지원되는 북미판(USA) 게임이 아닙니다."
    if "not a supported build" in text or "must be the unpatched 1.0" in text:
        return "clean USA 1.0 원본이 아니거나 이미 수정된 파일입니다."
    if report.reasons:
        return "지원되지 않는 원본입니다: " + report.reasons[0]
    return "지원되지 않는 원본입니다."


class QueueWriter(io.TextIOBase):
    def __init__(self, events: queue.Queue):
        self.events = events
        self.pending = ""

    def write(self, text: str) -> int:
        self.pending += text.replace("\r", "")
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            if line.strip() and not line.startswith(("save:", "load:")):
                self.events.put(("log", line))
        return len(text)

    def flush(self) -> None:
        if self.pending.strip():
            self.events.put(("log", self.pending.strip()))
        self.pending = ""


class App(TkinterDnD.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITLE)
        self.geometry("700x500")
        self.minsize(650, 470)
        self.events: queue.Queue = queue.Queue()
        self.source: Path | None = None
        self.building = False

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="clean USA 1.0 CCI/3DS를 선택하거나 창 안으로 끌어다 놓으세요.").pack(anchor="w")
        row = ttk.Frame(outer)
        row.pack(fill="x", pady=(5, 10))
        self.path_var = tk.StringVar(value="파일을 선택하세요.")
        self.path_entry = ttk.Entry(row, textvariable=self.path_var, state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True)
        self.choose_button = ttk.Button(row, text="원본 CCI/3DS 선택", command=self.choose_file)
        self.choose_button.pack(side="left", padx=(8, 0))
        for widget in (outer, row, self.path_entry):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self.drop_file)

        guide = ttk.LabelFrame(outer, text="버전 선택", padding=(10, 6))
        guide.pack(fill="x", pady=(0, 10))
        ttk.Label(guide, text="구형 3DS·2DS  →  1.0 권장  ·  CPP가 없어 1.1 패치가 사실상 필요하지 않습니다.").pack(anchor="w")
        ttk.Label(guide, text="New 3DS·New 2DS·에뮬레이터  →  1.1 권장  ·  공식 1.1 수정 + CPP 자동 활성화").pack(anchor="w", pady=(3, 0))
        ttk.Label(
            guide,
            text="1.1 완성본은 타이틀 화면에 ‘1.1’이 표시되면 정상입니다. 에뮬레이터 CPP 감도는 낮게 권장합니다.",
            foreground="#555555",
        ).pack(anchor="w", pady=(3, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(0, 10))
        self.build10 = ttk.Button(
            buttons, text="1.0 빌드 (CPP 없음)", command=lambda: self.start_build("1.0"), state="disabled"
        )
        self.build10.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.build11 = ttk.Button(
            buttons, text="1.1 빌드 (CPP 포함)", command=lambda: self.start_build("1.1"), state="disabled"
        )
        self.build11.pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(outer, text=WAIT_NOTICE, foreground="#555555").pack(anchor="w", pady=(0, 6))

        self.status_var = tk.StringVar(value="원본 CCI/3DS를 선택해 주세요.")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100, variable=self.progress_var)
        self.progress.pack(fill="x", pady=(4, 8))
        self.log = tk.Text(outer, height=8, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        ttk.Label(outer, text="참고: " + LUMA_WARNING, foreground="#9a4b00", wraplength=660).pack(
            fill="x", pady=(8, 0)
        )
        self.after(100, self.poll_events)

    def append_log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_build_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled and not self.building else "disabled"
        self.build10.configure(state=state)
        self.build11.configure(state=state)

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="clean USA 1.0 CCI/3DS 선택",
            filetypes=(("Nintendo 3DS 이미지", "*.cci *.3ds"), ("모든 파일", "*.*")),
        )
        if selected:
            self.inspect_file(Path(selected))

    def drop_file(self, event) -> str:
        if self.building:
            self.append_log("빌드 중에는 다른 원본을 넣을 수 없습니다.")
            return "break"
        paths = self.tk.splitlist(event.data)
        if len(paths) != 1:
            self.append_log("CCI/3DS 파일은 하나만 넣어 주세요.")
            return "break"
        path = Path(paths[0])
        if path.suffix.lower() not in (".cci", ".3ds"):
            self.status_var.set("CCI 또는 3DS 파일을 넣어 주세요.")
            self.append_log("원본 확인 실패: CCI/3DS 파일이 아닙니다.")
            return "break"
        self.inspect_file(path)
        return "break"

    def inspect_file(self, path: Path) -> None:
        report = patcher.Report()
        try:
            patcher.inspect_base(path, report)
        except (OSError, patcher.InspectError) as exc:
            self.source = None
            self.path_var.set(str(path))
            self.status_var.set("원본을 읽을 수 없습니다.")
            self.append_log(f"실패: {exc}")
            self.set_build_buttons(False)
            return
        self.path_var.set(str(path))
        if report.supported:
            self.source = path
            self.status_var.set("지원되는 clean USA 1.0 원본입니다.")
            self.append_log("원본 확인 완료: clean USA 1.0")
            self.set_build_buttons(True)
        else:
            self.source = None
            reason = short_reason(report)
            self.status_var.set(reason)
            self.append_log("원본 확인 실패: " + reason)
            self.set_build_buttons(False)

    def output_path(self, track: str) -> Path:
        assert self.source is not None
        base = self.source.with_name(f"{self.source.stem}_Korean_{track}.cci")
        if not base.exists():
            return base
        number = 2
        while True:
            candidate = base.with_name(f"{base.stem}_{number}{base.suffix}")
            if not candidate.exists():
                return candidate
            number += 1

    def start_build(self, track: str) -> None:
        if self.building or self.source is None:
            return
        self.building = True
        self.choose_button.configure(state="disabled")
        self.set_build_buttons(False)
        self.progress_var.set(0)
        self.status_var.set(f"{track} 빌드를 생성하는 중입니다. 시간이 좀 걸리니 기다려 주세요…")
        self.append_log(f"{track} 빌드 시작")
        output = self.output_path(track)
        threading.Thread(target=self.run_build, args=(track, output), daemon=True).start()

    def run_build(self, track: str, output: Path) -> None:
        assert self.source is not None
        writer = QueueWriter(self.events)
        try:
            with tempfile.TemporaryDirectory(prefix=f"mgs3d-{track}-") as work:
                def report_progress(percent: int, message: str) -> None:
                    self.events.put(("progress", (percent, message)))

                args = argparse.Namespace(
                    base=self.source, track=track, out=output, workdir=Path(work),
                    progress=report_progress,
                )
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    result = patcher.command_build(args)
                writer.flush()
            if result == 0:
                self.events.put(("success", str(output.resolve())))
            else:
                self.events.put(("failure", "빌드 검증에 실패했습니다. 아래 로그를 확인하세요."))
        except Exception as exc:
            writer.flush()
            self.events.put(("failure", str(exc)))

    def poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.append_log(value)
                elif kind == "progress":
                    percent, message = value
                    self.progress_var.set(percent)
                    self.status_var.set(f"{percent}% · {message}")
                elif kind == "success":
                    self.finish_build(True, value)
                elif kind == "failure":
                    self.finish_build(False, value)
        except queue.Empty:
            pass
        self.after(100, self.poll_events)

    def finish_build(self, success: bool, value: str) -> None:
        self.building = False
        self.progress_var.set(100 if success else 0)
        self.choose_button.configure(state="normal")
        self.set_build_buttons(self.source is not None)
        if success:
            self.status_var.set("완료: " + value)
            self.append_log("완료: " + value)
            messagebox.showinfo(TITLE, "패치된 CCI 생성이 완료되었습니다.\n\n" + value)
        else:
            self.status_var.set("실패: " + value)
            self.append_log("실패: " + value)
            messagebox.showerror(TITLE, "CCI 생성에 실패했습니다.\n\n" + value)


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
