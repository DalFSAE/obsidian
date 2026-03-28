"""
add-crossrefs.py
Adds markdown cross-reference links to the FSAE rules markdown files.

Run after convert-pdf.py:
    python3 add-crossrefs.py

Each occurrence of a rule ID (e.g. F.3.2.1) or section reference
(e.g. "section PS", "section F.4.2") in body text is turned into a
clickable markdown link pointing to the correct heading in the correct file.
"""

from pathlib import Path
import re

MD_DIR = Path(__file__).parent.parent / "FSAE Rules 2026 V1"

SECTION_CODES = ["GR", "AD", "PS", "VE", "EV", "IC", "IN", "V", "F", "T", "S", "D"]

# Rule ID: one or more uppercase letters, then one or more .digit groups
RULE_ID_PAT = r"[A-Z]{1,3}(?:\.\d+)+"


def github_anchor(heading_text: str) -> str:
    """
    Compute the GitHub-flavored markdown anchor id for a heading line.
    Strips leading '#' markers and applies GFM rules:
      - lowercase
      - remove anything that isn't alphanumeric, space, or hyphen
      - collapse spaces to hyphens
    """
    text = heading_text.lstrip("#").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)   # keep letters, digits, _, spaces, -
    text = re.sub(r"\s+", "-", text.strip())
    return text


def build_index(md_dir: Path) -> tuple[dict, dict]:
    """
    Returns:
      rule_index   – {rule_id: (filename, anchor)}
      section_index – {section_code: filename}
    """
    rule_index: dict[str, tuple[str, str]] = {}
    section_index: dict[str, str] = {}

    heading_re = re.compile(r"^(#+)\s+(.+)$")
    rule_id_re = re.compile(r"^(" + RULE_ID_PAT + r")\b")
    section_h1_re = re.compile(r"^([A-Z]{1,3})\s*[–-]\s*.+")

    for md_file in sorted(md_dir.glob("*.md")):
        filename = md_file.name
        for line in md_file.read_text(encoding="utf-8").splitlines():
            m = heading_re.match(line)
            if not m:
                continue

            heading_text = m.group(2)
            anchor = github_anchor(line)   # pass the full heading line for accuracy

            # H1 section headings like "# GR – General Regulations"
            if m.group(1) == "#":
                sec = section_h1_re.match(heading_text)
                if sec and sec.group(1) in SECTION_CODES:
                    section_index[sec.group(1)] = filename

            # Any heading whose text starts with a rule ID
            rid = rule_id_re.match(heading_text)
            if rid:
                rule_id = rid.group(1)
                rule_index[rule_id] = (filename, anchor)

    return rule_index, section_index


def make_link(text: str, filename: str, anchor: str, current_file: str) -> str:
    if filename == current_file:
        return f"[{text}](#{anchor})"
    return f"[{text}]({filename}#{anchor})"


def process_line(
    line: str,
    current_file: str,
    rule_index: dict,
    section_index: dict,
) -> str:
    """
    Return the line with rule ID and section references replaced by
    markdown links.  Heading lines and already-linked text are left alone.
    """
    # Never modify heading lines — the IDs there are definitions, not references
    if line.lstrip().startswith("#"):
        return line

    # ── 1. Replace "section CODE[.N.N]" patterns ─────────────────────────────
    # e.g. "section PS", "section F.4.2", "section IC.4"
    def replace_section(m: re.Match) -> str:
        code = m.group("code")
        digits = m.group("digits")          # may be None

        if digits:
            # "section F.4.2" → link to rule F.4.2
            full_id = f"{code}.{digits}"
            if full_id in rule_index:
                fname, anchor = rule_index[full_id]
                return f"section [{full_id}]({fname}#{anchor})" if fname != current_file \
                    else f"section [{full_id}](#{anchor})"
            # Rule not found; fall back to section file link
        if code in section_index:
            fname = section_index[code]
            target = fname if fname != current_file else ""
            label = f"{code}.{digits}" if digits else code
            if fname != current_file:
                return f"section [{label}]({fname})"
            return m.group(0)   # same file, don't create a circular link

        return m.group(0)   # unknown section, leave unchanged

    code_alt = "|".join(SECTION_CODES)
    section_re = re.compile(
        r"\bsection\s+(?P<code>" + code_alt + r")"
        r"(?:\.(?P<digits>\d+(?:\.\d+)*))?"
    )
    line = section_re.sub(replace_section, line)

    # ── 2. Replace bare rule IDs ──────────────────────────────────────────────
    # Match a rule ID that is NOT:
    #   - immediately preceded by '[' (already a link label)
    #   - immediately preceded by a word character (mid-word)
    #   - followed by ']' (already inside brackets)
    # Strip a trailing letter sub-item (.a .n etc.) before looking up.
    rule_ref_re = re.compile(
        r"(?<!\[)(?<!\w)"
        r"(" + RULE_ID_PAT + r")"
        r"(?:\.[a-z])?"     # optional letter sub-item — not part of the anchor
        r"(?!\])"
    )

    def replace_rule(m: re.Match) -> str:
        full_match = m.group(0)
        rule_id = m.group(1)           # without the optional letter suffix
        suffix = full_match[len(rule_id):]  # e.g. ".n" or ""

        if rule_id in rule_index:
            fname, anchor = rule_index[rule_id]
            link = make_link(rule_id, fname, anchor, current_file)
            return link + suffix

        return full_match  # unknown rule, leave unchanged

    line = rule_ref_re.sub(replace_rule, line)

    return line


def add_crossrefs(md_dir: Path) -> None:
    print("Building index...")
    rule_index, section_index = build_index(md_dir)
    print(f"  Found {len(rule_index)} rule headings across "
          f"{len(set(f for f, _ in rule_index.values()))} files")
    print(f"  Found {len(section_index)} sections")

    print("Adding cross-reference links...")
    for md_file in sorted(md_dir.glob("*.md")):
        current_file = md_file.name
        lines = md_file.read_text(encoding="utf-8").splitlines()
        new_lines = [
            process_line(line, current_file, rule_index, section_index)
            for line in lines
        ]
        md_file.write_text("\n".join(new_lines), encoding="utf-8")
        print(f"  {current_file}")

    print("\nDone.")


if __name__ == "__main__":
    add_crossrefs(MD_DIR)
