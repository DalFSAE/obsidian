from pathlib import Path
import re

from pypdf import PdfReader


PDF_PATH = Path(__file__).parent.parent / "PDFs" / "FSAE_Rules_2026_V1.pdf"
OUT_DIR = Path(__file__).parent.parent / "FSAE Rules 2026 V1"
OUT_DIR.mkdir(exist_ok=True)

# Top-level section codes in the rules
SECTION_CODES = [
    "GR", "AD", "PS", "V", "F", "T", "VE", "IC", "EV", "IN", "S", "D",
]

# Regex to detect a big section heading like "GR - GENERAL REGULATIONS" or "GR – General Regulations"
# Title must be mostly uppercase to avoid false positives on table/paragraph lines
SECTION_HEADER_RE = re.compile(
    r"^(?P<code>(" + "|".join(SECTION_CODES) + r"))\s*[-–]\s*(?P<title>[^.]{3,})$"
)

# Acronyms that should stay uppercase when converting all-caps titles to title case
KNOWN_ACRONYMS = {
    "SAE", "IC", "EV", "VE", "AD", "GR", "PS", "IN", "PDF", "XLSX",
    "CAD", "CFD", "FEA", "ESF", "AIP", "AMB", "SES", "BOM",
    "AC", "DC", "HV", "LV", "EMI", "PCB", "BMS",
}

# Rule ID like GR.1, GR.1.1, F.2.3.4 (with optional inline content after a space)
RULE_ID_RE = re.compile(
    r"^(?P<id>[A-Z]{1,3}\.\d+(?:\.\d+)*)\s*(?P<content>.*)$"
)

# Lines that look like page headers/footers we want to drop
HEADER_FOOTER_PATTERNS = [
    re.compile(r"^Formula SAE® Rules 2026"),
    re.compile(r"^Version 1\.0"),
    re.compile(r"^Page \d+ of \d+", re.IGNORECASE),
    re.compile(r"^Verify this is the current version", re.IGNORECASE),
]


def is_header_footer(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    return any(p.search(line) for p in HEADER_FOOTER_PATTERNS)


def is_toc_page(lines: list[str]) -> bool:
    """A page is a TOC page if a significant fraction of non-empty lines contain dot sequences."""
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return False
    toc_lines = sum(1 for l in non_empty if re.search(r"\.{5,}", l))
    return toc_lines / len(non_empty) > 0.25


def is_mostly_uppercase(text: str) -> bool:
    """Return True if >85% of alphabetic characters are uppercase."""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return False
    return sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.85


def title_case_if_all_caps(text: str) -> str:
    """Convert ALL CAPS text to Title Case, preserving known acronyms."""
    if not is_mostly_uppercase(text):
        return text
    words = text.split()
    result = []
    for word in words:
        core = word.strip("®.,;:()/-")
        if core in KNOWN_ACRONYMS:
            result.append(word)  # keep acronym as-is
        else:
            result.append(word.capitalize())
    return " ".join(result)


def sanitize_filename(text: str) -> str:
    """Create a reasonable filename slug from a section title."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def rule_depth(rule_id: str) -> int:
    """
    Return the nesting depth of a rule ID.
    GR.1 → 1, GR.1.1 → 2, GR.1.1.1 → 3
    """
    parts = rule_id.split(".")
    return len(parts) - 1  # subtract 1 for the prefix (GR, F, etc.)


def depth_to_heading(depth: int) -> str:
    """Map rule depth to a markdown heading prefix. Depth 1 → ##, depth 2 → ###, etc."""
    # Clamp between 2 and 5 hashes
    hashes = min(max(depth + 1, 2), 5)
    return "#" * hashes


# Words that signal the START of a sentence (not a title word)
_SENTENCE_STARTERS = {
    "A", "An", "The", "All", "Each", "Any", "Every", "Some", "No",
    "This", "These", "Those", "If", "When", "Where",
}


def split_title_content(text: str) -> tuple[str, str]:
    """
    Try to split a rule's inline text into (short_title, body_text).

    Returns ("", full_text) when no title can be detected — meaning the
    entire text is the rule sentence and should stay as body content.

    Detects three patterns where a title precedes the body:
      1. Article/determiner starts the body:
            "Driver Suit A one piece suit..."  →  ("Driver Suit", "A one piece suit...")
      2. First title word is repeated at the start of the body:
            "Socks Socks made from..."          →  ("Socks", "Socks made from...")
      3. Enumeration marker (a., b., ...) starts the body:
            "Arm Restraints a. Arm restraints…" →  ("Arm Restraints", "a. Arm restraints…")

    Non-title sentences (no split) are detected when:
      • The first word is itself a sentence-starter ("The", "Each", …)
      • The first word leads directly into a lowercase word ("Teams will", "SAE … and")
    """
    words = text.split()
    if not words:
        return "", ""

    # Content that starts with an article/determiner is a sentence from word 0
    if words[0] in _SENTENCE_STARTERS or words[0][0].islower():
        return "", text

    split_at = None
    for i in range(1, min(7, len(words))):
        w = words[i]

        if w in _SENTENCE_STARTERS:          # e.g. "Driver Suit  A  one piece…"
            split_at = i
            break

        if w.lower() == words[i - 1].lower():  # e.g. "Socks  Socks  made from…"
            split_at = i
            break

        if re.match(r"^[a-z]\.$", w):          # e.g. "Arm Restraints  a.  …"
            split_at = i
            break

        if w[0].islower():                     # lowercase word ends the title region
            break                              # no sentence-starter found → no split

    if split_at:
        return " ".join(words[:split_at]), " ".join(words[split_at:])
    return "", text


# Matches a standalone letter list marker: not preceded by letter/digit,
# single lowercase letter, period, one or more spaces, then uppercase or '('
_LETTER_MARKER_RE = re.compile(r"(?<![A-Za-z0-9])([a-z])\. +(?=[A-Z\(])")
_BULLET_SPLIT_RE = re.compile(r"\s*•\s*")


def _split_inline_lettered(text: str):
    """
    Detect and split an inline lettered list like "preamble: a. item b. item c. item".

    Returns (lead_in: str, items: list[(letter, text)]) if a valid list is found,
    or None if no list is detected.

    A sequence is considered a valid list when:
    - The letters are consecutive starting from 'a', OR
    - There are ≥2 sequential letter markers (e.g. b. c. d.)
    """
    markers = list(_LETTER_MARKER_RE.finditer(text))
    if not markers:
        return None

    letters = [m.group(1) for m in markers]

    # Require letters to form a consecutive sequence
    ords = [ord(l) for l in letters]
    if not all(b == a + 1 for a, b in zip(ords, ords[1:])):
        return None  # non-sequential → not a list

    # Require at least 2 items OR a single 'a.' preceded by ':' or start-of-string
    if len(markers) == 1:
        before = text[: markers[0].start()].rstrip()
        if letters[0] != "a" or (before and not before.endswith(":")):
            return None

    lead_in = text[: markers[0].start()].rstrip()
    items = []
    for idx, m in enumerate(markers):
        start = m.end()
        end = markers[idx + 1].start() if idx + 1 < len(markers) else len(text)
        items.append((m.group(1), text[start:end].strip()))

    return lead_in, items


def expand_block(text: str) -> list[str]:
    """
    Expand a text block that may contain inline lists into separate markdown lines.

    Handles:
    - Lettered lists:   "must: a. Be hot b. Be cold"
                        → ["must:", "", "a. Be hot", "b. Be cold"]
    - Nested bullets:   "b. Conditions: • Case 1 • Case 2"
                        → ["b. Conditions:", "   - Case 1", "   - Case 2"]
    - Bare bullet list: "• item1 • item2"
                        → ["- item1", "- item2"]
    - Leading bullet:   "• item"   → ["- item"]
    """
    if not text.strip():
        return [text]

    list_data = _split_inline_lettered(text)
    if list_data:
        lead_in, items = list_data
        out = []
        if lead_in:
            out.append(lead_in)
            out.append("")
        for letter, item_text in items:
            if "•" in item_text:
                parts = _BULLET_SPLIT_RE.split(item_text)
                item_lead = parts[0].rstrip()
                bullets = [p.strip() for p in parts[1:] if p.strip()]
                out.append(f"{letter}. {item_lead}" if item_lead else f"{letter}.")
                for b in bullets:
                    out.append(f"   - {b}")
            else:
                out.append(f"{letter}. {item_text}")
        return out

    # No lettered list — handle inline/leading bullets
    if "•" in text:
        parts = _BULLET_SPLIT_RE.split(text)
        out = []
        lead = parts[0].rstrip()
        if lead:
            out.append(lead)
        for p in parts[1:]:
            if p.strip():
                out.append(f"- {p.strip()}")
        return out if out else [text]

    return [text]


def convert_bullets(lines: list[str]) -> list[str]:
    """Replace any remaining • bullet characters at the start of a line with - ."""
    result = []
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith("•"):
            line = " " * indent + "- " + stripped[1:].lstrip()
        result.append(line)
    return result


def extract_pages(pdf_path: Path) -> list[list[str]]:
    """Extract each PDF page as a list of cleaned lines."""
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines = []
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not is_header_footer(line):
                lines.append(line)
        pages.append(lines)
    return pages


def split_into_sections(pages: list[list[str]]):
    """
    Yield (code, title, [lines...]) for each top-level section.
    TOC pages are skipped entirely.
    """
    current_code = None
    current_title = None
    current_lines: list[str] = []

    for page_lines in pages:
        if is_toc_page(page_lines):
            continue

        for line in page_lines:
            m = SECTION_HEADER_RE.match(line.strip())
            if m and is_mostly_uppercase(m.group("title")):
                if current_code is not None:
                    yield current_code, current_title, current_lines
                current_code = m.group("code")
                raw_title = m.group("title").strip()
                current_title = title_case_if_all_caps(raw_title)
                current_lines = [f"# {current_code} – {current_title}", ""]
            else:
                if current_code is not None:
                    current_lines.append(line)

    if current_code is not None:
        yield current_code, current_title, current_lines


def process_section_lines(lines: list[str]) -> list[str]:
    """
    Convert raw section lines to well-formed markdown:
    - Proper heading hierarchy based on rule ID depth
    - Merge PDF-wrapped continuation lines into the rule paragraph
    - Convert bullet characters
    """
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Pass through the H1 section header unchanged
        if stripped.startswith("# ") and not stripped.startswith("## "):
            result.append(line)
            i += 1
            continue

        # Pass through blank lines
        if not stripped:
            result.append(line)
            i += 1
            continue

        m = RULE_ID_RE.match(stripped)
        if m:
            rule_id = m.group("id")
            inline_content = m.group("content").strip()
            depth = rule_depth(rule_id)
            heading_prefix = depth_to_heading(depth)

            if depth >= 3:
                # Leaf rule: the inline text IS the rule content. Merge any
                # following lines that are word-wrap continuations (not a blank
                # line, not a new rule ID, not a new section header).
                parts = [inline_content] if inline_content else []
                j = i + 1
                while j < len(lines):
                    next_stripped = lines[j].strip()
                    if not next_stripped:
                        break
                    if RULE_ID_RE.match(next_stripped):
                        break
                    if SECTION_HEADER_RE.match(next_stripped):
                        break
                    parts.append(next_stripped)
                    j += 1

                full_text = " ".join(parts)
                title, body = split_title_content(full_text)

                if title:
                    # Named item: short heading, then body as paragraph/list
                    result.append(f"{heading_prefix} {rule_id} {title}")
                    result.append("")
                    if body:
                        result.extend(expand_block(body))
                    result.append("")
                elif full_text:
                    # No named title — check whether the text contains an inline list
                    list_data = _split_inline_lettered(full_text)
                    if list_data:
                        lead_in, _ = list_data
                        if lead_in:
                            result.append(f"{heading_prefix} {rule_id} {lead_in}")
                        else:
                            result.append(f"{heading_prefix} {rule_id}")
                        result.append("")
                        # emit list items (expand_block returns [lead_in, "", item, ...])
                        # skip the lead_in line(s) since they're already in the heading
                        for expanded in expand_block(full_text):
                            if expanded != lead_in:
                                result.append(expanded)
                    else:
                        result.append(f"{heading_prefix} {rule_id} {full_text}")
                    result.append("")
                else:
                    result.append(f"{heading_prefix} {rule_id}")
                    result.append("")
                i = j  # skip the consumed continuation lines
            else:
                # Section/subsection heading: inline text is just the title.
                # Do NOT merge following paragraph content into the heading.
                title = title_case_if_all_caps(inline_content)
                if title:
                    result.append(f"{heading_prefix} {rule_id} {title}")
                else:
                    result.append(f"{heading_prefix} {rule_id}")
                result.append("")
                i += 1
        else:
            # Regular body paragraph — expand any inline lists/bullets
            result.extend(expand_block(line))
            i += 1

    result = convert_bullets(result)
    return result


def main():
    # Remove stale markdown files from previous runs
    for old_file in OUT_DIR.glob("*.md"):
        old_file.unlink()

    print(f"Reading {PDF_PATH}...")
    pages = extract_pages(PDF_PATH)
    print(f"  Extracted {len(pages)} pages")

    toc_count = sum(1 for p in pages if is_toc_page(p))
    print(f"  Skipping {toc_count} TOC pages")

    for code, title, raw_lines in split_into_sections(pages):
        print(f"  Writing section {code} – {title}")
        processed_lines = process_section_lines(raw_lines)

        name = f"{code.lower()}-{sanitize_filename(title)}.md"
        out_path = OUT_DIR / name
        out_path.write_text("\n".join(processed_lines), encoding="utf-8")

    print(f"\nDone. Markdown files written to: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
