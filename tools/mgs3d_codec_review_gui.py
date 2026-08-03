#!/usr/bin/env python3
"""Windows GUI for prioritizing untranslated MGS3D codec rows."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "ps2_korean"
REVIEW = ANALYSIS / "codec-untranslated-review.csv"
SELECTION = ANALYSIS / "codec-priority-output"
FILES = ANALYSIS / "codec-priority-files"
CODEC = ANALYSIS / "staging_media_minimal" / "codec.dat"
CANDIDATE = ANALYSIS / "codec_translation_static_media_191.json"
BASE_SELECTED = ANALYSIS / "codec_selected_static_media_191_fixed.json"
BASE_REPORT = ANALYSIS / "codec_selection_static_media_191_fixed_report.json"
ALLOCATION = ANALYSIS / "static_media_allocation_191.json"
SNA01 = ANALYSIS / "integrated_191_candidate" / "romfs" / "stage" / "r_sna01" / "resident.hpk"
SNA02 = ANALYSIS / "integrated_191_candidate" / "romfs" / "stage" / "r_sna02" / "resident.hpk"
TOOL = ROOT / "tools" / "mgs3d_codec_untranslated_select.py"

PROPER_NOUNS = (
    ("소콜로프", "Sokolov"), ("스네이크", "Snake"),
    ("오셀롯", "Ocelot"), ("볼긴", "Volgin"),
    ("더 보스", "The Boss"), ("제로 소령", "Major Zero"),
    ("패러메딕", "Para-Medic"), ("에바", "EVA"),
    ("그라닌", "Granin"), ("라이코프", "Raikov"),
    ("후르시초프", "Khrushchev"),
)


class ReviewApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MGS3D 미번역 한글 선택 도구")
        self.root.geometry("1450x850")
        self.rows: list[dict[str, str]] = []
        self.by_id: dict[str, dict[str, str]] = {}
        self.current_id: str | None = None
        self.busy = False
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="검색").pack(side="left")
        self.search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search, width=45)
        entry.pack(side="left", padx=6)
        self.search.trace_add("write", lambda *_: self._refresh())
        ttk.Label(top, text="표시").pack(side="left", padx=(12, 2))
        self.filter_mode = tk.StringVar(value="전체 미번역")
        mode = ttk.Combobox(
            top, textvariable=self.filter_mode, state="readonly", width=18,
            values=("전체 미번역", "선택한 문장", "글자 부족", "문자열 공간 부족"),
        )
        mode.pack(side="left")
        mode.bind("<<ComboboxSelected>>", lambda _event: self._refresh())
        ttk.Button(top, text="보이는 문장 선택", command=self._select_visible).pack(side="left", padx=8)
        ttk.Button(top, text="모두 해제", command=self._clear_all).pack(side="left")

        columns = ("selected", "priority", "gcx", "resource", "reason", "english", "korean")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", selectmode="browse")
        labels = {
            "selected": "선택", "priority": "우선", "gcx": "GCX", "resource": "문장",
            "reason": "현재 미번역 이유", "english": "현재 영어", "korean": "공식 한글",
        }
        widths = {"selected": 55, "priority": 55, "gcx": 60, "resource": 65,
                  "reason": 120, "english": 450, "korean": 500}
        for column in columns:
            self.tree.heading(column, text=labels[column])
            self.tree.column(column, width=widths[column], stretch=column in {"english", "korean"})
        scroll = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0))
        scroll.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._row_selected)
        self.tree.bind("<Double-1>", self._toggle_current)
        self.tree.bind("<space>", self._toggle_current)

        side = ttk.Frame(self.root, padding=10, width=370)
        side.pack(side="right", fill="y")
        self.count_label = ttk.Label(side, text="")
        self.count_label.pack(anchor="w", pady=(0, 8))
        ttk.Label(side, text="공식 한글 문장").pack(anchor="w")
        self.official = tk.Text(side, width=48, height=9, wrap="word", state="disabled")
        self.official.pack(fill="x", pady=(2, 8))
        ttk.Label(side, text="혼합 문장 (비우면 공식 한글 사용)").pack(anchor="w")
        self.replacement = tk.Text(side, width=48, height=9, wrap="word")
        self.replacement.pack(fill="x", pady=(2, 5))
        ttk.Button(side, text="고유명사를 영어로 변환", command=self._proper_nouns).pack(fill="x")
        ttk.Button(side, text="문장 수정 적용", command=self._apply_replacement).pack(fill="x", pady=(4, 12))
        ttk.Separator(side).pack(fill="x", pady=5)
        ttk.Button(side, text="1. 선택 저장", command=self._save).pack(fill="x", pady=3)
        ttk.Button(side, text="2. 용량 계산", command=lambda: self._run(False)).pack(fill="x", pady=3)
        ttk.Button(side, text="3. 계산 + RomForge 파일 생성", command=lambda: self._run(True)).pack(fill="x", pady=3)
        ttk.Button(side, text="결과 폴더 열기", command=self._open_output).pack(fill="x", pady=3)
        ttk.Separator(side).pack(fill="x", pady=8)
        ttk.Label(side, text="진행 결과").pack(anchor="w")
        self.log = tk.Text(side, width=48, height=15, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

    @staticmethod
    def _identifier(row: dict[str, str]) -> str:
        return f"{int(row['gcx'])}:{int(row['resource'])}"

    def _load(self) -> None:
        if not REVIEW.is_file():
            messagebox.showerror("파일 없음", f"미번역 목록이 없습니다.\n{REVIEW}")
            self.root.destroy()
            return
        with REVIEW.open(encoding="utf-8-sig", newline="") as stream:
            self.rows = list(csv.DictReader(stream))
        for row in self.rows:
            row.setdefault("replacement", "")
        self.by_id = {self._identifier(row): row for row in self.rows}
        self._refresh()

    def _matches(self, row: dict[str, str]) -> bool:
        query = self.search.get().strip().casefold()
        if query and query not in " ".join((row["english"], row["korean"], row.get("replacement", ""), row["gcx"], row["resource"])).casefold():
            return False
        mode = self.filter_mode.get()
        selected = row.get("accept", "").strip().lower() in {"yes", "1", "한글"}
        if mode == "선택한 문장" and not selected:
            return False
        if mode == "글자 부족" and row["reason"] != "static_glyph":
            return False
        if mode == "문자열 공간 부족" and row["reason"] != "string_capacity":
            return False
        return True

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        visible = 0
        selected_total = 0
        for row in self.rows:
            selected = row.get("accept", "").strip().lower() in {"yes", "1", "한글"}
            selected_total += selected
            if not self._matches(row):
                continue
            identifier = self._identifier(row)
            reason = "글자 부족" if row["reason"] == "static_glyph" else "문자열 공간"
            korean = row.get("replacement", "") or row["korean"]
            self.tree.insert("", "end", iid=identifier, values=(
                "✓" if selected else "", row["priority"], row["gcx"], row["resource"],
                reason, row["english"].replace("<0A>", " / "), korean.replace("<0A>", " / "),
            ))
            visible += 1
        self.count_label.configure(text=f"전체 {len(self.rows):,} / 표시 {visible:,} / 선택 {selected_total:,}")

    def _row_selected(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.current_id = selection[0]
        row = self.by_id[self.current_id]
        self.official.configure(state="normal")
        self.official.delete("1.0", "end")
        self.official.insert("1.0", row["korean"])
        self.official.configure(state="disabled")
        self.replacement.delete("1.0", "end")
        self.replacement.insert("1.0", row.get("replacement", ""))

    def _toggle_current(self, _event=None) -> None:
        if not self.current_id:
            return
        row = self.by_id[self.current_id]
        selected = row.get("accept", "").strip().lower() in {"yes", "1", "한글"}
        if selected:
            row["accept"] = ""
        else:
            row["accept"] = "yes"
            priorities = [int(item["priority"]) for item in self.rows
                          if item.get("accept", "").strip().lower() in {"yes", "1", "한글"}]
            row["priority"] = str(max(priorities, default=0) + 1)
        self._refresh()
        if self.tree.exists(self.current_id):
            self.tree.selection_set(self.current_id)

    def _select_visible(self) -> None:
        priorities = [int(item["priority"]) for item in self.rows
                      if item.get("accept", "").strip().lower() in {"yes", "1", "한글"}]
        next_priority = max(priorities, default=0) + 1
        for identifier in self.tree.get_children():
            row = self.by_id[identifier]
            if row.get("accept", "").strip().lower() not in {"yes", "1", "한글"}:
                row["accept"] = "yes"
                row["priority"] = str(next_priority)
                next_priority += 1
        self._refresh()

    def _clear_all(self) -> None:
        if not messagebox.askyesno("모두 해제", "선택한 문장을 모두 해제할까요?"):
            return
        for row in self.rows:
            row["accept"] = ""
        self._refresh()

    def _proper_nouns(self) -> None:
        if not self.current_id:
            return
        current = self.replacement.get("1.0", "end-1c") or self.by_id[self.current_id]["korean"]
        for korean, english in PROPER_NOUNS:
            current = current.replace(korean, english)
        self.replacement.delete("1.0", "end")
        self.replacement.insert("1.0", current)

    def _apply_replacement(self) -> bool:
        if not self.current_id:
            return True
        row = self.by_id[self.current_id]
        value = self.replacement.get("1.0", "end-1c").strip()
        if value and "<00>" not in value:
            messagebox.showerror("제어문자 필요", "문장 끝의 <00>을 지우면 안 됩니다.")
            return False
        row["replacement"] = "" if value == row["korean"] else value
        self._refresh()
        return True

    def _save(self) -> bool:
        if self.current_id:
            if not self._apply_replacement():
                return False
        fieldnames = list(self.rows[0])
        if "replacement" not in fieldnames:
            fieldnames.insert(fieldnames.index("note"), "replacement")
        with REVIEW.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.rows)
        self._append_log(f"저장 완료: {REVIEW}\n")
        return True

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run(self, build_files: bool) -> None:
        if self.busy or not self._save():
            return
        if not any(row.get("accept", "").strip().lower() in {"yes", "1", "한글"} for row in self.rows):
            messagebox.showinfo("선택 없음", "먼저 한글로 우선할 문장을 선택하세요.")
            return
        self.busy = True
        self._append_log("용량 계산을 시작합니다...\n")
        threading.Thread(target=self._worker, args=(build_files,), daemon=True).start()

    def _worker(self, build_files: bool) -> None:
        select_command = [
            sys.executable, str(TOOL), "select", str(CODEC), str(CANDIDATE),
            str(BASE_SELECTED), str(BASE_REPORT), str(ALLOCATION), str(REVIEW), str(SELECTION),
        ]
        completed = subprocess.run(select_command, text=True, capture_output=True)
        output = completed.stdout + completed.stderr
        if completed.returncode == 0 and build_files:
            build_command = [
                sys.executable, str(TOOL), "build-files", str(CODEC),
                str(SELECTION / "codec_selected.json"), str(SELECTION / "static_allocation.json"),
                str(SNA01), str(SNA02), str(FILES),
            ]
            built = subprocess.run(build_command, text=True, capture_output=True)
            output += built.stdout + built.stderr
            completed = built
        self.root.after(0, self._worker_done, completed.returncode, output, build_files)

    def _worker_done(self, returncode: int, output: str, built: bool) -> None:
        self.busy = False
        self._append_log(output + "\n")
        if returncode:
            messagebox.showerror("실패", "계산에 실패했습니다. 진행 결과를 확인하세요.")
        else:
            target = FILES if built else SELECTION
            messagebox.showinfo("완료", f"완료했습니다.\n{target}")

    def _open_output(self) -> None:
        target = FILES if FILES.exists() else SELECTION
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)  # type: ignore[attr-defined]


def main() -> int:
    root = tk.Tk()
    ReviewApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
