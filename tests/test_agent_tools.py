from app.agent_tools import ToolRunContext
from app.config import get_settings
from app.text_search import OfficialTextSearch


def test_search_tool_returns_traceable_official_results():
    tools = ToolRunContext(OfficialTextSearch(get_settings()))
    result = tools.execute("search_official_sources", {"query": "банковская карта стоп-лист задолженность", "top_k": 4})
    assert result["ok"] is True
    assert result["results"]
    assert all(row["result_id"] and row["source_id"] and row["url"] for row in result["results"])


def test_get_source_details_returns_neighbors():
    tools = ToolRunContext(OfficialTextSearch(get_settings()))
    search = tools.execute("search_official_sources", {"query": "утеря социальной транспортной карты"})
    detail = tools.execute("get_source_details", {"result_id": search["results"][0]["result_id"], "neighbor_count": 1})
    assert detail["ok"] is True
    assert detail["results"]


def test_fare_calculator_rejects_unverified_rate():
    tools = ToolRunContext(OfficialTextSearch(get_settings()))
    result = tools.execute("calculate_fare", {"distance_km": 25, "fare_per_km": 4.46})
    assert result["ok"] is False
    assert "not found" in result["error"]
