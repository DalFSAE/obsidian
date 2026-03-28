from pathlib import Path
import re

from pypdf import PdfReader


PDF_PATH = Path("FSAE_Rules_2026_V1.pdf")
OUT_DIR = Path("fsae_rules_2026_md")
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


def convert_bullets(lines: list[str]) -> list[str]:
    """Replace • bullet characters with markdown - bullets."""
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
                if full_text:
                    result.append(f"{heading_prefix} {rule_id} {full_text}")
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
            result.append(line)
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
