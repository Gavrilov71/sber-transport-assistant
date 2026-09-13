"""Official-data-only route identification. No model or fuzzy carrier fallback."""
import json
import re
from datetime import date
from pathlib import Path

from .municipalities import normalize_municipality

ROUTES = json.loads((Path(__file__).parent / 'data' / 'routes.json').read_text(encoding='utf-8'))


def normalize_route_number(text: str) -> str | None:
    value = text.lower().replace('ё', 'е')
    match = re.search(r'(?<!\w)№?\s*(\d{1,4})\s*([а-яa-z]?)(?!\w)', value)
    return (match.group(1) + match.group(2)) if match else None


def _current(route: dict) -> bool:
    return bool(route.get('verified') and (not route.get('valid_from') or date.fromisoformat(route['valid_from']) <= date.today()) and (not route.get('valid_to') or date.fromisoformat(route['valid_to']) >= date.today()))


def _candidates(rows: list[dict]) -> list[dict]:
    # Unselected matches must not hand an LLM an unverified carrier choice.
    return [{key: row[key] for key in ('route_number', 'municipality', 'name', 'source_url')}
            for row in rows]


def resolve_route(facts: dict) -> dict:
    number = normalize_route_number(str(facts.get('route_number') or ''))
    municipality = normalize_municipality(str(facts.get('municipality') or '')) or facts.get('municipality')
    origin = normalize_municipality(str(facts.get('origin') or ''))
    destination = normalize_municipality(str(facts.get('destination') or ''))
    transport_type = facts.get('transport_type')
    if not number and not (origin and destination):
        return {'status': 'needs_clarification', 'matches': [], 'route': None,
                'missing_fields': ['route_number']}
    matches = [row for row in ROUTES if _current(row) and (not number or row['normalized_number'] == number)]
    if transport_type:
        matches = [row for row in matches if row['transport_type'] == transport_type]
    if municipality:
        matches = [row for row in matches if municipality in row['served_municipalities']]
    if origin and destination:
        matches = [row for row in matches if {origin, destination} <= set(row['served_municipalities'])
                   and row.get('origin') and row.get('destination')]
    if not matches:
        return {'status': 'not_found', 'matches': [], 'route': None, 'missing_fields': []}
    if not number:
        return {'status': 'needs_clarification', 'matches': _candidates(matches), 'route': None,
                'missing_fields': ['route_number']}
    # The source tables cover a selected area, not every route in the region. A
    # number alone is therefore insufficient evidence of regional uniqueness.
    if not municipality and not (origin and destination):
        return {'status': 'needs_clarification', 'matches': _candidates(matches), 'route': None,
                'missing_fields': ['municipality']}
    if len(matches) > 1:
        return {'status': 'ambiguous', 'matches': _candidates(matches), 'route': None,
                'missing_fields': ['route_number'] if not number else ['origin', 'destination']}
    return {'status': 'resolved', 'matches': matches, 'route': matches[0], 'missing_fields': []}
