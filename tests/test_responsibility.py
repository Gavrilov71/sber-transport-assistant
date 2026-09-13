from app.responsibility import ResponsibilityRouter
from app.municipalities import normalize_municipality, REGISTRY


def test_rules_and_anti_hallucination():
    router = ResponsibilityRouter()
    cases = [
        ({"issue_type": "bank_card_payment", "municipality": "novomoskovsk"}, "oeirc"),
        ({"issue_type": "payment_problem"}, "oeirc"),
        ({"issue_type": "missed_trip", "municipality": "tula"}, "amo_tula"),
        ({"issue_type": "missed_trip", "municipality": "novomoskovsk"}, "amo_novomoskovsk"),
        ({"issue_type": "missed_trip", "municipality": "uzlovaya"}, "orgpn"),
        ({"issue_type": "missed_trip", "route_scope": "intermunicipal"}, "orgpn"),
        ({"issue_type": "unsafe_driver"}, "rostransnadzor_tula"),
        ({"issue_type": "vehicle_defect_hazard"}, "rostransnadzor_tula"),
    ]
    for facts, expected in cases:
        result = router.resolve(facts)
        assert result["status"] == "resolved"
        assert result["primary_authority"]["id"] == expected
    assert router.resolve({"issue_type": "missed_trip"})["status"] == "needs_clarification"
    assert router.resolve({"issue_type": "unknown"})["primary_authority"] is None
    for authority in router.authorities.values():
        if not authority["appeal_verified"]:
            assert authority["appeal_url"] is None


def test_municipality_registry():
    assert len(REGISTRY) >= 26
    for text, expected in [("Узловая", "uzlovaya"), ("в Узловой", "uzlovaya"),
                           ("Новомосковск", "novomoskovsk"), ("в Новомосковске", "novomoskovsk"),
                           ("Щекино", "schekino"), ("Щёкино", "schekino")]:
        assert normalize_municipality(text) == expected
