"""Build a checked route registry from the project's official OEIRC snapshots."""
import json
import re
from pathlib import Path
from app.municipalities import normalize_municipality

ROOT = Path(__file__).parent
snapshots = json.loads((ROOT / 'app/data/source_snapshots.json').read_text(encoding='utf-8'))
records = []
seen = set()
for source_id in ('oeirc-routes-wallet', 'oeirc-routes-subscription'):
    source = next(row for row in snapshots if row['id'] == source_id)
    text = source['text']
    for number, name, operator in re.findall(r'\n\s*Тула\nАвтобус\n([^\n]+)\n([^\n]+)\n([^\n]+)', text):
        number, name, operator = (x.strip() for x in (number, name, operator))
        normalized = re.sub(r'\s+', '', number.lower().replace('ё', 'е'))
        identity = (normalized, name, operator)
        if identity in seen:
            continue
        seen.add(identity)
        origin = destination = None
        parts = re.split(r'\s+[-–—]\s+', name)
        if len(parts) == 2:
            origin, destination = (x.strip() for x in parts)
        served = ['tula']
        for endpoint in (origin, destination):
            place = normalize_municipality(endpoint or '')
            if place and place not in served:
                served.append(place)
        records.append({
            'route_number': number, 'normalized_number': normalized,
            'transport_type': 'bus', 'municipality': 'tula', 'route_scope': None,
            'name': name, 'origin': origin, 'destination': destination,
            'operator': operator, 'organizer': None,
            'served_municipalities': served,
            'source_url': source['url'], 'source_type': 'oeirc',
            'verified': True, 'verified_at': source['fetched_at'][:10],
            'valid_from': None, 'valid_to': None,
        })

# The official ORGPN route documents identify the scope and endpoints.
documents = {
    '208': ('Узловая', 'Тула', 'uzlovaya', 'https://orgpn.ru/files/reestr_marshruta/megmunitspal/208_uzlovaya_tula.pdf'),
    '114': ('Щёкино', 'Тула', 'schekino', 'https://orgpn.ru/files/reestr_marshruta/megmunitspal/114_Tula_Shekino_s_01052022.pdf'),
}
for number, (origin, destination, other_municipality, url) in documents.items():
    # The OEIRC table has one matching number and matching endpoint pair for each document.
    matches = [row for row in records if row['normalized_number'] == number and all(
        point.lower().replace('ё', 'е') in row['name'].lower().replace('ё', 'е')
        for point in (origin, destination))]
    assert len(matches) == 1, (number, matches)
    row = matches[0]
    row['municipality'] = None  # A cross-municipal route has no single municipality.
    row['route_scope'] = 'intermunicipal'
    row['origin'], row['destination'] = origin, destination
    row['served_municipalities'] = ['tula', other_municipality]
    row['scope_source_url'] = url

records.sort(key=lambda x: (x['normalized_number'], x['name']))
(ROOT / 'app/data/routes.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{len(records)} verified route records')
