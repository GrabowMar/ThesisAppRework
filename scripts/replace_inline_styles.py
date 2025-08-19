import re
import hashlib
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / 'src' / 'templates'
THEME_CSS = ROOT / 'src' / 'static' / 'css' / 'theme.css'

STYLE_ATTR_RE = re.compile(r"style=\"([^\"]+)\"", re.IGNORECASE)
CLASS_ATTR_RE = re.compile(r"class=\"([^\"]*)\"", re.IGNORECASE)

OCCURRENCE_THRESHOLD = 3


def normalize_style(style_str: str) -> str:
    # Remove HTML entity encodings and whitespace
    s = style_str.strip().strip(';')
    # Split into declarations, strip spaces
    parts = [p.strip() for p in s.split(';') if p.strip()]
    # Split key:value and normalize spacing
    kv = []
    for p in parts:
        if ':' not in p:
            continue
        k, v = p.split(':', 1)
        kv.append((k.strip().lower(), v.strip()))
    # Sort by property name for stable fingerprint
    kv.sort(key=lambda x: x[0])
    return '; '.join(f"{k}: {v}" for k, v in kv)


def is_dynamic(style_str: str) -> bool:
    s = style_str.lower()
    if '{{' in s or '}}' in s:
        return True
    # contains percentages likely dynamic widths; allow if not contains template
    return False


def collect_styles():
    counter = Counter()
    occurrences = defaultdict(list)  # norm_style -> list of (path, matchobj)

    for html_path in TEMPLATES_DIR.rglob('*.html'):
        text = html_path.read_text(encoding='utf-8', errors='ignore')
        for m in STYLE_ATTR_RE.finditer(text):
            raw = m.group(1)
            if is_dynamic(raw):
                continue
            norm = normalize_style(raw)
            # Ignore very short or trivial one-offs like display:none (bootstrap has d-none)
            if not norm or len(norm) < 5:
                continue
            occurrences[norm].append((html_path, m.span()))
            counter[norm] += 1

    return counter, occurrences


def class_name_for(style_norm: str) -> str:
    # Known mappings for readability
    known = {
        'max-height: 420px; overflow: auto; white-space: pre-wrap': 'pre-wrap-max420',
        'max-height: 500px; overflow: auto; white-space: pre-wrap': 'pre-wrap-max500',
        'height: 300px': 'h-300px',
        'height: 400px': 'h-400px',
        'position: relative; height: 70vh': 'pos-rel-h-70vh',
        'position: relative; height: 300px': 'pos-rel-h-300',
    }
    if style_norm in known:
        return known[style_norm]
    digest = hashlib.sha1(style_norm.encode('utf-8')).hexdigest()[:6]
    return f"u-{digest}"


def generate_css(classes_map):
    lines = ["\n/* ===== Auto-generated utility classes for inline styles ===== */\n"]
    for style_norm, cls in classes_map.items():
        lines.append(f"/* {style_norm} */\n.{cls} {{ {style_norm}; }}\n")
    return ''.join(lines)


def apply_replacements(target_styles, occurrences, classes_map):
    # For each file, apply replacements in one pass
    files_changes = 0
    for html_path in set(p for occs in occurrences.values() for (p, _) in occs):
        text = html_path.read_text(encoding='utf-8', errors='ignore')
        # Build replacements: find all style attributes and if norm in target, replace
        new_text = text
        changed = False

        def repl(match):
            raw = match.group(1)
            norm = normalize_style(raw)
            if norm not in target_styles:
                return match.group(0)
            cls = classes_map[norm]
            # Simpler: rebuild around this style attr replacement only
            # Replace style="..." with nothing and inject class into the element's class attribute
            # We'll do a conservative approach by: remove style attribute, then add class before >
            return f"data-inline-style-replaced=\"{cls}\""

        # First pass: mark style attributes for replacement with a temp attribute carrying class
        new_text2 = STYLE_ATTR_RE.sub(repl, new_text)
        if new_text2 != new_text:
            new_text = new_text2
            changed = True

        if changed:
            # Now convert data-inline-style-replaced attributes into class augmentation
            def add_class_attr(m):
                # m.group(0) is entire tag start like <div ...>
                tag = m.group(0)
                # Extract class attr if present
                cls_added = []
                for m2 in re.finditer(r'data-inline-style-replaced=\"([^\"]+)\"', tag):
                    cls_added.append(m2.group(1))
                if not cls_added:
                    return tag
                tag_clean = re.sub(r'\sdata-inline-style-replaced=\"[^\"]+\"', '', tag)
                class_m = re.search(r'class=\"([^\"]*)\"', tag_clean)
                if class_m:
                    current = class_m.group(1)
                    # inject new classes if not present
                    new_classes = current.split()
                    for c in cls_added:
                        if c not in new_classes:
                            new_classes.append(c)
                    return tag_clean.replace(class_m.group(0), f'class="{' '.join(new_classes)}"')
                else:
                    # insert class attribute before closing '>'
                    return tag_clean.replace('>', f' class="{' '.join(cls_added)}">', 1)

            # Apply to opening tags only by a simple heuristic: replace in <tag ...>
            new_text3 = re.sub(r'<([a-zA-Z0-9\-]+)([^>]*)>', lambda m: add_class_attr(m), new_text)
            if new_text3 != new_text:
                new_text = new_text3

            # Finally, remove any remaining temporary attributes (if any)
            new_text = re.sub(r'\sdata-inline-style-replaced=\"[^\"]+\"', '', new_text)

            html_path.write_text(new_text, encoding='utf-8')
            files_changes += 1

    return files_changes


def main():
    counter, occurrences = collect_styles()
    # Filter by threshold
    target_styles = {s for s, c in counter.items() if c >= OCCURRENCE_THRESHOLD}
    if not target_styles:
        print("No repeated inline styles found above threshold; no changes made.")
        return
    print(f"Found {len(target_styles)} repeated inline style patterns (>= {OCCURRENCE_THRESHOLD} uses).")

    classes_map = {s: class_name_for(s) for s in target_styles}
    css = generate_css(classes_map)

    with THEME_CSS.open('a', encoding='utf-8') as f:
        f.write('\n' + css)

    files_changed = apply_replacements(target_styles, occurrences, classes_map)
    print(f"Updated {files_changed} files to replace inline style attributes with utility classes.")
    print("Classes added:")
    for s, cls in classes_map.items():
        print(f".{cls} -> {s}")


if __name__ == '__main__':
    main()
