import json
import math
import re
from collections import Counter
from dataclasses import dataclass

from rapidfuzz.fuzz import token_set_ratio

from .config import Settings
from .municipalities import normalize_municipality


def source_applicable(source: dict, context: dict | None = None) -> bool:
    """Fail closed when a source's documented coverage exceeds known context."""
    context = context or {}
    scope = source.get("scope", "unknown")
    if scope == "region":
        return True
    if scope == "municipality":
        city = str(context.get("municipality") or "")
        return bool(city and source.get("municipality") == (normalize_municipality(city) or city))
    if scope == "operator":
        return bool(context.get("operator") and source.get("operator") == context["operator"])
    if scope == "route_specific":
        return bool(source.get("route_number") and context.get("route_number") == source["route_number"])
    return False


STOPWORDS = {
    "и", "в", "во", "на", "не", "что", "как", "для", "ли", "а", "по", "с", "со",
    "у", "из", "к", "ко", "при", "это", "где", "можно", "могу", "сейчас", "щас",
}


def normalize_tokens(text: str) -> list[str]:
    words = re.findall(r"[a-zа-яё0-9]+", text.lower())
    result = []
    for word in words:
        if word in STOPWORDS:
            continue
        # A conservative Russian stem is enough for retrieval and avoids changing numbers/names.
        if len(word) > 6 and not word.isdigit():
            word = word[:6]
        result.append(word)
    return result


@dataclass
class SearchHit:
    row: dict
    score: float


class OfficialTextSearch:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sources = {row["id"]: row for row in self._load(settings.sources_path)}
        self.chunks = self._load(settings.chunks_path)
        self.by_id = {row["id"]: row for row in self.chunks if row.get("current", True)}
        self.by_source: dict[str, list[dict]] = {}
        self.tokens: dict[str, list[str]] = {}
        document_frequency: Counter[str] = Counter()
        for row in self.by_id.values():
            self.by_source.setdefault(row["source_id"], []).append(row)
            tokens = normalize_tokens(
                f"{row.get('title', '')} {row.get('category', '')} {row.get('text', '')}"
            )
            self.tokens[row["id"]] = tokens
            document_frequency.update(set(tokens))
        count = max(1, len(self.by_id))
        self.idf = {term: math.log(1 + (count - freq + 0.5) / (freq + 0.5))
                    for term, freq in document_frequency.items()}
        lengths = [len(tokens) for tokens in self.tokens.values()]
        self.average_length = sum(lengths) / max(1, len(lengths))

    @staticmethod
    def _load(path) -> list[dict]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, ValueError):
            return []

    @property
    def ready(self) -> bool:
        return bool(self.chunks)

    def search(self, query: str, category: str | None = None, top_k: int = 5,
               context: dict | None = None) -> list[SearchHit]:
        query_tokens = normalize_tokens(query)
        if not query_tokens:
            return []
        query_text = " ".join(query_tokens)
        hits = []
        for row_id, row in self.by_id.items():
            if not source_applicable(self.sources.get(row["source_id"], {}), context):
                continue
            row_category = str(row.get("category", ""))
            if category and category.lower() not in row_category.lower():
                continue
            tokens = self.tokens[row_id]
            frequencies = Counter(tokens)
            length = len(tokens)
            bm25 = 0.0
            for term in query_tokens:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + 1.2 * (1 - 0.75 + 0.75 * length / max(1, self.average_length))
                bm25 += self.idf.get(term, 0) * frequency * 2.2 / denominator
            fuzzy = token_set_ratio(query_text, " ".join(tokens)) / 100
            phrase = 1.0 if query.lower() in row.get("text", "").lower() else 0.0
            numbers = re.findall(r"\d+(?:[,.]\d+)?", query)
            number_bonus = 0.8 if numbers and all(number in row.get("text", "") for number in numbers) else 0
            priority = max(0, min(100, int(row.get("priority", 50)))) / 100
            score = bm25 + 1.4 * fuzzy + 1.2 * phrase + number_bonus + 0.18 * priority
            if score > 0.35:
                hits.append(SearchHit(row=row, score=round(score, 4)))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:max(1, min(top_k, 8))]

    def details(self, result_id: str, neighbor_count: int = 1,
                context: dict | None = None) -> list[dict]:
        row = self.by_id.get(result_id)
        if not row or not source_applicable(self.sources.get(row["source_id"], {}), context):
            return []
        source_rows = self.by_source.get(row["source_id"], [])
        try:
            index = next(i for i, candidate in enumerate(source_rows) if candidate["id"] == result_id)
        except StopIteration:
            return [row]
        start = max(0, index - max(0, min(neighbor_count, 2)))
        end = min(len(source_rows), index + max(0, min(neighbor_count, 2)) + 1)
        return source_rows[start:end]
