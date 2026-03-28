# DalFSAE Rules

Competition rules for the Dalhousie Formula SAE team.

## Contents

| Folder / File | Description |
|---|---|
| `FSAE Rules 2026 V1/` | FSAE 2026 rules converted to Markdown |
| `PDFs/` | Source PDFs |
| `tools/` | Conversion scripts |

## FSAE 2026 Markdown Rules

Each section of the rulebook is a separate file:

| File | Section |
|---|---|
| `gr-general-regulations.md` | GR – General Regulations |
| `ad-administrative-regulations.md` | AD – Administrative Regulations |
| `ps-pre-competition-submissions.md` | PS – Pre-Competition Submissions |
| `v-vehicle-requirements.md` | V – Vehicle Requirements |
| `f-chassis-and-structural.md` | F – Chassis and Structural |
| `t-technical-aspects.md` | T – Technical Aspects |
| `ve-vehicle-and-driver-equipment.md` | VE – Vehicle and Driver Equipment |
| `ic-internal-combustion-engine-vehicles.md` | IC – Internal Combustion Engine Vehicles |
| `ev-electric-vehicles.md` | EV – Electric Vehicles |
| `in-technical-inspection.md` | IN – Technical Inspection |
| `s-static-events.md` | S – Static Events |
| `d-dynamic-events.md` | D – Dynamic Events |

Rules are formatted with a heading hierarchy matching the rule numbering (`##` for top-level sections, `###` for subsections, `####` for individual rules). Lettered and bulleted lists are expanded into proper Markdown lists. Rule IDs in body text are linked to their definitions.

## Regenerating the Markdown

From the `tools/` directory:

```bash
# Convert the PDF to Markdown
python3 convert-pdf.py

# Add cross-reference links between rules
python3 add-crossrefs.py
```

Requires Python 3.10+ and `pypdf`:

```bash
pip install pypdf
```
