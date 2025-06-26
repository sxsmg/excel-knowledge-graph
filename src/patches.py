# src/patches.py
"""
Tiny utilities we monkey-patch into Llama-Index so the Cypher that
reaches Neo4j is always fence-free.
"""

import re

_TICKS = re.compile(
     r"^```(?:cypher)?\s*|\s*```$",
     re.IGNORECASE
 )

def clean_cypher(raw: str | None) -> str:
    """Strip leading/trailing ``` or ```cypher fences (and surrounding whitespace)."""
    if raw is None:
        return ""
    text = _TICKS.sub("", raw).strip()
    return text.strip("` \n")
