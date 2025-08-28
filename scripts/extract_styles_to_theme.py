import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / 'src' / 'templates'
THEME_CSS = ROOT / 'src' / 'static' / 'css' / 'theme.css'

STYLE_RE = re.compile(r"<style[^>]*>([\s\S]*?)</style>", re.IGNORECASE)


def extract_and_move_styles():
    appended_css_chunks = []
    changed_files = []

    for html_path in TEMPLATES_DIR.rglob('*.html'):
        text = html_path.read_text(encoding='utf-8', errors='ignore')
        matches = list(STYLE_RE.finditer(text))
        if not matches:
            continue

        css_blocks = [m.group(1).strip() for m in matches if m.group(1).strip()]
        if not css_blocks:
            # Remove empty <style> tags if any
            new_text = STYLE_RE.sub('', text)
            if new_text != text:
                html_path.write_text(new_text, encoding='utf-8')
                changed_files.append(str(html_path.relative_to(ROOT)))
            continue

        rel = html_path.relative_to(ROOT)
        header = f"\n\n/* ===== Extracted from {rel.as_posix()} ===== */\n"
        css_to_append = header + "\n\n".join(css_blocks) + "\n"

        # Special handling: if this is print layout, wrap in @media print
        if 'layouts/print.html' in rel.as_posix():
            css_to_append = f"\n\n/* ===== Extracted from {rel.as_posix()} (print-only) ===== */\n@media print {{\n{indent_lines('\n\n'.join(css_blocks), 2)}\n}}\n"

        appended_css_chunks.append(css_to_append)

        # Remove the <style> blocks from the HTML
        new_text = STYLE_RE.sub('', text)
        if new_text != text:
            html_path.write_text(new_text, encoding='utf-8')
            changed_files.append(str(rel))

    if appended_css_chunks:
        with THEME_CSS.open('a', encoding='utf-8') as f:
            f.write("\n\n/* ===== BEGIN: Auto-extracted inline <style> blocks ===== */\n")
            for chunk in appended_css_chunks:
                f.write(chunk)
            f.write("/* ===== END: Auto-extracted inline <style> blocks ===== */\n")

    return changed_files, bool(appended_css_chunks)


def indent_lines(s: str, spaces: int) -> str:
    pad = ' ' * spaces
    return '\n'.join(pad + line if line.strip() else line for line in s.splitlines())


if __name__ == '__main__':
    changed, appended = extract_and_move_styles()
    print(f"Updated {len(changed)} HTML files to remove <style> blocks.")
    for p in changed:
        print(f" - {p}")
    print(f"Appended CSS to theme.css: {'yes' if appended else 'no'}")
