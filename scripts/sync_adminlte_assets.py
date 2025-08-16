"""
Sync AdminLTE assets from repo-level /dist into src/static/vendor/adminlte.

This avoids runtime dependence on /dist while keeping templates aligned with AdminLTE.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SRC_STATIC = ROOT / "src" / "static"
VENDOR = SRC_STATIC / "vendor" / "adminlte"

CSS_SRC = DIST / "css"
JS_SRC = DIST / "js"
CSS_DST = VENDOR / "css"
JS_DST = VENDOR / "js"

FILES_CSS = [
    "adminlte.min.css",
    "adminlte.min.css.map",
    "adminlte.css",
    "adminlte.css.map",
    "adminlte.rtl.min.css",
    "adminlte.rtl.min.css.map",
]

FILES_JS = [
    "adminlte.min.js",
    "adminlte.min.js.map",
    "adminlte.js",
    "adminlte.js.map",
]

def copy_files(src_dir: Path, dst_dir: Path, files: list[str]):
    dst_dir.mkdir(parents=True, exist_ok=True)
    for name in files:
        src = src_dir / name
        dst = dst_dir / name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"Copied {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
        else:
            print(f"Skip (not found): {src.relative_to(ROOT)}")

def main():
    if not DIST.exists():
        raise SystemExit("dist folder not found — nothing to sync")
    VENDOR.mkdir(parents=True, exist_ok=True)
    copy_files(CSS_SRC, CSS_DST, FILES_CSS)
    copy_files(JS_SRC, JS_DST, FILES_JS)
    print("Sync complete.")

if __name__ == "__main__":
    main()
