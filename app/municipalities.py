"""Deterministic municipality normalization for the Tula region."""
import json
import re
from pathlib import Path

REGISTRY = json.loads((Path(__file__).parent / "data" / "municipalities.json").read_text(encoding="utf-8"))


def municipalities_in(text: str) -> list[str]:
    normalized = re.sub(r"[^\w\s-]", " ", text.lower().replace("ё", "е"))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    matches = []
    for row in REGISTRY:
        for alias in row["aliases"]:
            alias = alias.lower().replace("ё", "е")
            if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized):
                matches.append(row["id"])
                break
    return matches


def normalize_municipality(text: str) -> str | None:
    matches = municipalities_in(text)
    return matches[0] if len(matches) == 1 else None
