# parser.py

import re

# crude extractor: finds all occurrences like A1, $B$2, Sheet1!C3
CELL_REF_RE = re.compile(r"(?:'([^']+)'|([A-Za-z0-9_]+))?!?(\$?[A-Za-z]+\$?\d+)")

def extract_dependencies(formula: str):
    """
    Returns a list of raw cell coordinates (e.g. ["A1", "B2"]) found in the formula.
    """
    matches = CELL_REF_RE.findall(formula)
    deps = []
    for sheet_name, plain_sheet, coord in matches:
        deps.append(coord)
    return deps
