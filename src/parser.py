# parser.py

import re

# Matches:
#   'My Sheet'!A1, MySheet!A1, A1, $B$2, A1:B2, 'Other Sheet'!A3:C5
CELL_REF_RE = re.compile(
    r"(?:'(?P<sheet_quoted>[^']+)'|(?P<sheet_unquoted>[A-Za-z0-9_ ]+))?!?"
    r"(?P<start>\$?[A-Za-z]+\$?\d+)"
    r"(?:\s*:\s*(?P<end>\$?[A-Za-z]+\$?\d+))?"
)

def extract_dependencies(formula: str):
    """
    Extract all sheet-qualified and unqualified cell refs and ranges.
    Returns a list of (sheet_name_or_None, coord_or_range) tuples.
    """
    deps = []
    for m in CELL_REF_RE.finditer(formula):
        sheet = (m.group('sheet_quoted') or m.group('sheet_unquoted') or "").strip() or None
        start = m.group('start').replace('$','')
        end = m.group('end')
        if end:
            end = end.replace('$','')
            deps.append((sheet, f"{start}:{end}"))
        else:
            deps.append((sheet, start))
    return deps
