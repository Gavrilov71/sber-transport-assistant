import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .text_search import OfficialTextSearch
from .responsibility import ResponsibilityRouter, resolve_route


FUNCTIONS = [
    {"name": "get_emergency_guidance", "description": "Проверенные действия и номер экстренной помощи ТОЛЬКО при явно продолжающейся сейчас опасной поездке, например «мы сейчас едем». Одна фраза «водитель пьяный» без времени не доказывает непосредственную угрозу: сначала уточни время. При явной текущей угрозе вызывай прежде формального маршрутизатора жалобы.", "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "resolve_responsibility", "description": "Определяет компетентный орган только по проверенным правилам. Обязателен для жалобы или вопроса куда обратиться.", "parameters": {"type": "object", "properties": {"issue_type": {"type": "string"}, "municipality": {"type": "string"}, "route_number": {"type": "string"}, "route_scope": {"type": "string"}, "operator": {"type": "string"}, "transport_type": {"type": "string"}, "card_type": {"type": "string"}, "safety_related": {"type": "boolean"}}, "required": ["issue_type"]}},
    {"name": "resolve_route", "description": "Определяет маршрут, перевозчика и территорию только по официальному реестру; при неоднозначности требует уточнение.", "parameters": {"type": "object", "properties": {"municipality": {"type": "string"}, "route_number": {"type": "string"}, "origin": {"type": "string"}, "destination": {"type": "string"}, "transport_type": {"type": "string"}}, "required": []}},
    {
        "name": "search_official_sources",
        "description": (
            "Ищет актуальные сведения в локальном корпусе официальных источников общественного "
            "транспорта Тульской области. Формулируй самостоятельный точный поисковый запрос; "
            "если результатов недостаточно, вызови функцию повторно с другими терминами."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Нормализованный поисковый запрос на русском языке"},
                "category": {"type": "string", "description": "Необязательная категория источника"},
                "top_k": {"type": "integer", "description": "Число результатов от 1 до 8"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_source_details",
        "description": "Возвращает полный найденный фрагмент и соседние фрагменты того же официального источника.",
        "parameters": {
            "type": "object",
            "properties": {
                "result_id": {"type": "string", "description": "result_id из search_official_sources"},
                "neighbor_count": {"type": "integer", "description": "Число соседних фрагментов: 0–2"},
            },
            "required": ["result_id"],
        },
    },
    {
        "name": "calculate_fare",
        "description": (
            "Безопасно рассчитывает стоимость по расстоянию и тарифу за км. Вызывай только после "
            "того, как ровно этот тариф найден функцией поиска в официальном источнике."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "distance_km": {"type": "number", "description": "Подтвержденное расстояние в километрах"},
                "fare_per_km": {"type": "number", "description": "Тариф за километр из результата поиска"},
            },
            "required": ["distance_km", "fare_per_km"],
        },
    },
]


@dataclass
class ToolRunContext:
    search: OfficialTextSearch
    context: dict = field(default_factory=dict)
    result_rows: dict[str, dict] = field(default_factory=dict)
    source_rows: dict[str, dict] = field(default_factory=dict)
    allowed_per_km_fares: set[Decimal] = field(default_factory=set)
    responsibility_result: dict | None = None
    route_result: dict | None = None
    emergency_result: dict | None = None

    def public_row(self, row: dict, score: float | None = None, full: bool = False) -> dict:
        source = self.search.sources.get(row["source_id"], {})
        result = {
            "result_id": row["id"], "source_id": row["source_id"], "title": row.get("title"),
            "url": row.get("url"), "category": row.get("category"), "priority": row.get("priority"),
            "scope": source.get("scope", "unknown"),
            "municipality": source.get("municipality"), "operator": source.get("operator"),
            "fetched_at": row.get("fetched_at"),
            "text": row.get("text", "") if full else row.get("text", "")[:1400],
        }
        if score is not None:
            result["score"] = score
        return result

    def _remember(self, row: dict) -> None:
        self.result_rows[row["id"]] = row
        self.source_rows[row["source_id"]] = row
        text = row.get("text", "")
        for match in re.finditer(r"(\d+(?:[,.]\d+)?)\s*(?:₽|руб(?:ля|лей)?)[^\n.]{0,35}(?:за|/)\s*(?:1\s*)?(?:км|километр)", text, re.I):
            self.allowed_per_km_fares.add(Decimal(match.group(1).replace(",", ".")))

    def execute(self, name: str, arguments: dict) -> dict:
        if name == "get_emergency_guidance":
            data = json.loads((Path(__file__).parent / "data" / "emergency_guidance.json").read_text(encoding="utf-8"))
            self.emergency_result = data if data.get("verified") and data.get("source_url") else {"verified": False}
            return self.emergency_result
        if name == "resolve_responsibility":
            self.responsibility_result = ResponsibilityRouter().resolve(arguments)
            return self.responsibility_result
        if name == "resolve_route":
            self.route_result = resolve_route(arguments)
            if self.route_result.get("status") == "resolved":
                route = self.route_result.get("route") or {}
                for key in ("municipality", "route_number", "operator"):
                    if route.get(key):
                        self.context[key] = route[key]
            return self.route_result
        if name == "search_official_sources":
            query = str(arguments.get("query", "")).strip()
            if not query:
                return {"ok": False, "error": "query is required"}
            hits = self.search.search(query, arguments.get("category"), int(arguments.get("top_k", 5)), self.context)
            for hit in hits:
                self._remember(hit.row)
            return {"ok": True, "query": query, "results": [self.public_row(hit.row, hit.score) for hit in hits]}
        if name == "get_source_details":
            result_id = str(arguments.get("result_id", ""))
            rows = self.search.details(result_id, int(arguments.get("neighbor_count", 1)), self.context)
            for row in rows:
                self._remember(row)
            return {"ok": bool(rows), "result_id": result_id,
                    "results": [self.public_row(row, full=True) for row in rows],
                    **({} if rows else {"error": "result_id not found"})}
        if name == "calculate_fare":
            try:
                distance = Decimal(str(arguments["distance_km"]))
                fare = Decimal(str(arguments["fare_per_km"]))
            except (KeyError, InvalidOperation):
                return {"ok": False, "error": "distance_km and fare_per_km must be numbers"}
            if distance <= 0 or fare <= 0:
                return {"ok": False, "error": "values must be positive"}
            if fare not in self.allowed_per_km_fares:
                return {"ok": False, "error": "fare_per_km was not found in previous official tool results"}
            total = (distance * fare).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return {"ok": True, "distance_km": float(distance), "fare_per_km": float(fare),
                    "total": float(total), "currency": "RUB"}
        return {"ok": False, "error": f"unknown function: {name}"}
