"""Fail-closed routing of passenger complaints to verified competencies."""
import json
from pathlib import Path
from .municipalities import normalize_municipality

DATA = Path(__file__).parent / "data"
ISSUE_TYPES = {"fare_question", "benefit_question", "transport_card", "social_transport_card", "troika", "bank_card_payment", "payment_problem", "stop_list", "double_charge", "validator_problem", "schedule_violation", "missed_trip", "route_change", "route_information", "wrong_route", "no_stop", "driver_behavior", "vehicle_cleanliness", "vehicle_technical_condition", "vehicle_safety", "unsafe_driver", "vehicle_defect_hazard", "lost_property", "complaint_other", "unknown"}


class ResponsibilityRouter:
    def __init__(self):
        self.authorities = {a["id"]: a for a in json.loads((DATA / "authorities.json").read_text(encoding="utf-8"))}
        self.rules = json.loads((DATA / "responsibility_rules.json").read_text(encoding="utf-8"))
        for rule in self.rules:
            assert rule["primary_authority"] in self.authorities
            assert set(rule["issue_types"]) <= ISSUE_TYPES

    def resolve(self, facts: dict) -> dict:
        issue = str(facts.get("issue_type") or "unknown").lower()
        municipality = normalize_municipality(str(facts.get("municipality") or "")) or str(facts.get("municipality") or "").lower()
        scope = str(facts.get("route_scope") or "").lower()
        if issue not in ISSUE_TYPES or issue in {"unknown", "complaint_other", "lost_property", "fare_question", "benefit_question"}:
            return {"status": "needs_clarification" if issue in {"unknown", "complaint_other"} else "unresolved", "primary_authority": None, "reason": "Тип проблемы недостаточно определён для адресации.", "missing_fields": ["issue_type"] if issue in {"unknown", "complaint_other"} else [], "verified": False}
        if issue == "transport_card" and not facts.get("card_type"):
            return {"status": "needs_clarification", "primary_authority": None, "reason": "Уточните, какая карта не работает: банковская, «Тройка» или социальная?", "missing_fields": ["card_type"], "verified": False}
        if issue in {"schedule_violation", "missed_trip", "route_change", "route_information", "wrong_route", "no_stop", "driver_behavior", "vehicle_cleanliness"} and not municipality and scope != "intermunicipal":
            return {"status": "needs_clarification", "primary_authority": None, "reason": "Подскажите, в каком городе или на каком маршруте это произошло?", "missing_fields": ["municipality"], "verified": False}
        for rule in self.rules:
            if issue not in rule["issue_types"]:
                continue
            if "route_scope" in rule and scope != rule["route_scope"]:
                continue
            if "municipality" in rule and (scope == "intermunicipal" or (rule["municipality"] != "*" and municipality != rule["municipality"])):
                continue
            authority = self.authorities[rule["primary_authority"]].copy()
            authority["appeal_url"] = authority["appeal_url"] if authority["appeal_verified"] else None
            return {"status": "resolved", "primary_authority": authority, "reason": ", ".join(authority["responsibilities"]), "missing_fields": [], "verified": True}
        return {"status": "unresolved", "primary_authority": None, "reason": "Подтверждённый адресат не найден.", "missing_fields": [], "verified": False}


def resolve_route(facts: dict) -> dict:
    from .route_resolver import resolve_route as resolve_official_route
    return resolve_official_route(facts)
