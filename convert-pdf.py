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

# Regex to detect a big section heading like "GR - GENERAL REGULATIONS"
SECTION_HEADER_RE = re.compile(
    r"^(?P<code>(" + "|".join(SECTION_CODES) + r"))\s*-\s*(?P<title>.+)$"
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


def sanitize_filename(text: str) -> str:
    """Create a reasonable filename slug from a section title."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def extract_plain_text(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        # Split into lines, strip trailing whitespace
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not is_header_footer(line):
                lines.append(line)
        # Add a blank line between pages to help paragraph breaks
        lines.append("")
    return lines


def split_into_sections(lines: list[str]):
    """
    Yield (code, title, [lines...]) for each top-level section.
    """
    current_code = None
    current_title = None
    current_lines: list[str] = []

    for line in lines:
        m = SECTION_HEADER_RE.match(line.strip())
        if m:
            # We hit a new section; flush the previous one
            if current_code is not None:
                yield current_code, current_title, current_lines
            current_code = m.group("code")
            current_title = m.group("title").strip()
            current_lines = []
            # Store the header as an H1 in markdown
            current_lines.append(f"# {current_code} – {current_title}")
            current_lines.append("")  # blank line
        else:
            # Not a new section header
            if current_code is not None:
                current_lines.append(line)
            else:
                # Stuff before the first section (cover, ToC, etc.)
                # You can either discard this or put it in a separate file.
                pass

    # Final flush
    if current_code is not None:
        yield current_code, current_title, current_lines


def convert_subheadings_to_md(lines: list[str]) -> list[str]:
    """
    Optional: turn things like 'GR.1 FORMULA SAE COMPETITION OBJECTIVE'
    into markdown '## GR.1 Formula SAE Competition Objective'
    """
    new_lines: list[str] = []
    subheading_re = re.compile(r"^([A-Z]{1,3}\.\d+(\.\d+)*)\s+(.*)")

    for line in lines:
        stripped = line.strip()
        m = subheading_re.match(stripped)
        if m:
            rule_id = m.group(1)
            rest = m.group(3)
            new_lines.append(f"## {rule_id} {rest}")
        else:
            new_lines.append(line)
    return new_lines


def main():
    print(f"Reading {PDF_PATH}...")
    all_lines = extract_plain_text(PDF_PATH)

    for code, title, raw_lines in split_into_sections(all_lines):
        print(f"Writing section {code} – {title}")
        # Optional: post-process to add markdown sub-headings
        processed_lines = convert_subheadings_to_md(raw_lines)

        # Write to file
        name = f"{code.lower()}-{sanitize_filename(title)}.md"
        out_path = OUT_DIR / name
        out_path.write_text("\n".join(processed_lines), encoding="utf-8")

    print(f"Done. Markdown files are in: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()

