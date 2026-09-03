# PyInstaller onedir build. Run from the repository root:
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "tools/mgs3d_patcher_gui.py")],
    pathex=[str(root / "tools")],
    binaries=[
        (str(root / "experiments/repack_tools/3dstool/3dstool.exe"),
         "experiments/repack_tools/3dstool"),
    ],
    datas=[
        (str(root / "payload/standalone"), "payload/standalone"),
    ] + collect_data_files("tkinterdnd2"),
    hiddenimports=["tkinterdnd2"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mgs3d_kor_patcher_v0.94a1",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Packed executables are more likely to trigger heuristic antivirus
    # detections.  Prefer a slightly larger, transparent release binary.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="mgs3d_kor_patcher_v0.94a1",
)
