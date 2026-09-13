import threading
import time
import uuid
from copy import deepcopy
from .municipalities import REGISTRY, normalize_municipality
from .route_resolver import normalize_route_number

SLOTS = ("municipality", "route_number", "route_scope", "card_type", "payment_method", "benefit_category", "operator", "is_trip_ongoing")
SAFETY_ISSUES = {"unsafe_driver", "vehicle_defect_hazard", "accident"}
MUNICIPALITY_IDS = {row["id"] for row in REGISTRY}


def _slot_value(key: str, value):
    if key == "is_trip_ongoing":
        return value if isinstance(value, bool) else None
    if not isinstance(value, str) or not value.strip() or value.strip().lower() in {"unknown", "null"}:
        return None
    if key == "municipality":
        canonical = value.strip().lower()
        return canonical if canonical in MUNICIPALITY_IDS else normalize_municipality(value)
    if key == "route_number":
        return normalize_route_number(value)
    if key == "card_type":
        return canonical_card_type(value)
    if key == "route_scope":
        return value.strip().lower() if value.strip().lower() in {"municipal", "intermunicipal"} else None
    return value.strip()


def reconcile_state(previous_state: dict, model_patch: dict, tool_trace: list[dict],
                    explicit_slot_updates: dict | None = None) -> dict:
    """Merge supported facts by provenance, then enforce dialogue invariants."""
    state = deepcopy(previous_state)
    state.setdefault("slots", {key: None for key in SLOTS})
    patch = model_patch or {}
    for key in ("task_mode", "issue_type", "severity"):
        value = patch.get(key)
        if value not in (None, "", "unknown"):
            state[key] = "safety" if key == "task_mode" and value == "safety_emergency" else value
    for key, value in (patch.get("slots") or {}).items():
        if key in SLOTS and (normalized := _slot_value(key, value)) is not None:
            state["slots"][key] = normalized
    if "pending_clarification" in patch:
        state["pending_clarification"] = patch["pending_clarification"]
    if "last_resolved_facts" in patch:
        state["last_resolved_facts"] = patch["last_resolved_facts"]
    for call in tool_trace:
        name, result = call.get("name"), call.get("result") or {}
        if result.get("status") != "resolved":
            continue
        args = call.get("arguments") or {}
        keys = ("municipality", "route_number", "route_scope") if name == "resolve_responsibility" else ("route_number",) if name == "resolve_route" else ()
        for key in keys:
            if (normalized := _slot_value(key, args.get(key))) is not None:
                state["slots"][key] = normalized
        if name == "resolve_route":
            route = result.get("route") or {}
            for key in ("route_number", "route_scope", "operator"):
                if (normalized := _slot_value(key, route.get(key))) is not None:
                    state["slots"][key] = normalized
    for key, value in (explicit_slot_updates or {}).items():
        if key in SLOTS and (normalized := _slot_value(key, value)) is not None:
            state["slots"][key] = normalized
    pending = state.get("pending_clarification")
    if isinstance(pending, str) and pending in SLOTS and state["slots"].get(pending) is not None:
        state["pending_clarification"] = None
    if state.get("issue_type") in SAFETY_ISSUES and state.get("severity") == "normal":
        state["severity"] = "safety"
    if (state.get("issue_type") in SAFETY_ISSUES and state.get("severity") == "immediate_danger"
            and state["slots"].get("is_trip_ongoing") is not True):
        state["severity"] = "safety"
    if state.get("severity") == "immediate_danger":
        state["task_mode"] = "safety"
    return state


def canonical_card_type(value: str) -> str | None:
    """Normalize a closed card slot after the agent has seen the user turn."""
    forms = {
        "bank": "bank", "bank_card": "bank", "banking": "bank",
        "банковская": "bank", "банковской": "bank", "банковская карта": "bank", "банковской картой": "bank",
        "troika": "troika", "тройка": "troika", "тройкой": "troika", "тройку": "troika", "«тройка»": "troika",
        "social": "social", "social_card": "social", "социальная": "social", "социальной": "social",
        "социальная карта": "social", "социальной картой": "social", "стк": "social",
    }
    return forms.get(value.strip().lower().replace("ё", "е"))


def new_dialogue_state() -> dict:
    return {"task_mode": None, "issue_type": None, "severity": "normal",
            "slots": {key: None for key in SLOTS}, "pending_clarification": None,
            "last_resolved_facts": None}


class ConversationStore:
    def __init__(self, max_messages: int = 12, ttl_seconds: int = 6 * 60 * 60):
        self.max_messages = max_messages
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, dict] = {}
        self._lock = threading.RLock()

    def create(self) -> str:
        conversation_id = str(uuid.uuid4())
        with self._lock:
            self._items[conversation_id] = {"updated": time.time(), "messages": [], "state": new_dialogue_state()}
        return conversation_id

    def history(self, conversation_id: str | None) -> tuple[str, list[dict]]:
        now = time.time()
        with self._lock:
            for key in list(self._items):
                if now - self._items[key]["updated"] > self.ttl_seconds:
                    del self._items[key]
            if not conversation_id or conversation_id not in self._items:
                conversation_id = self.create()
            item = self._items[conversation_id]
            item["updated"] = now
            return conversation_id, list(item["messages"][-self.max_messages:])

    def append_turn(self, conversation_id: str, user: str, assistant: str) -> None:
        with self._lock:
            item = self._items.setdefault(conversation_id, {"updated": time.time(), "messages": []})
            item["messages"].extend(({"role": "user", "content": user}, {"role": "assistant", "content": assistant}))
            item["messages"] = item["messages"][-self.max_messages:]
            item["updated"] = time.time()

    def dialogue_state(self, conversation_id: str) -> dict:
        with self._lock:
            state = self._items[conversation_id].setdefault("state", new_dialogue_state())
            if state.get("task_mode") == "safety_emergency":
                state["task_mode"] = "safety"
            return deepcopy(state)

    def merge_state(self, conversation_id: str, patch: dict, tool_trace: list[dict] | None = None,
                    explicit_slot_updates: dict | None = None) -> dict:
        with self._lock:
            state = self._items[conversation_id].setdefault("state", new_dialogue_state())
            state = reconcile_state(state, patch, tool_trace or [], explicit_slot_updates)
            self._items[conversation_id]["state"] = state
            self._items[conversation_id]["updated"] = time.time()
            return deepcopy(state)

    def pending(self, conversation_id: str) -> dict | None:
        with self._lock:
            item = self._items.get(conversation_id)
            return dict(item["pending"]) if item and item.get("pending") else None

    def set_pending(self, conversation_id: str, state: dict | None) -> None:
        with self._lock:
            item = self._items.get(conversation_id)
            if item is not None:
                item["pending"] = dict(state) if state else None
                item["updated"] = time.time()

    def last_resolved(self, conversation_id: str) -> dict | None:
        with self._lock:
            item = self._items.get(conversation_id)
            return dict(item["last_resolved"]) if item and item.get("last_resolved") else None

    def set_last_resolved(self, conversation_id: str, state: dict | None) -> None:
        with self._lock:
            item = self._items.get(conversation_id)
            if item is not None:
                item["last_resolved"] = dict(state) if state else None
                item["updated"] = time.time()

    def clear(self, conversation_id: str) -> None:
        with self._lock:
            self._items.pop(conversation_id, None)
