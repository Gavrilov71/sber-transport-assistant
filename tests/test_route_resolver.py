from app.route_resolver import ROUTES, _current, normalize_route_number, resolve_route


def test_registry_and_normalization():
    assert len(ROUTES) >= 90
    for text in ("10Л", "10л", "10 л", "маршрут 10л", "автобус №10Л"):
        assert normalize_route_number(text) == "10л"


def test_verified_operators_and_no_guessing():
    ten = resolve_route({"route_number": "10Л", "municipality": "tula"})
    assert ten["status"] == "resolved"
    assert ten["route"]["operator"] == "ООО «ИРБИС»"
    assert resolve_route({"route_number": "208"})["status"] == "needs_clarification"
    assert resolve_route({"route_number": "39", "municipality": "tula"})["status"] == "not_found"
    assert resolve_route({"route_number": "39А", "municipality": "tula"})["status"] == "resolved"
    assert resolve_route({"route_number": "9999", "municipality": "tula"})["status"] == "not_found"


def test_intermunicipal_and_ambiguity():
    route = resolve_route({"route_number": "208", "municipality": "uzlovaya"})
    assert route["route"]["route_scope"] == "intermunicipal"
    assert "orgpn.ru" in route["route"]["scope_source_url"]
    assert resolve_route({"route_number": "181", "municipality": "tula"})["status"] == "ambiguous"
    assert _current({**route["route"], "valid_to": "2020-01-01"}) is False
