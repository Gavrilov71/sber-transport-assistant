from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=64)


class SourceItem(BaseModel):
    title: str
    url: str | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    status: Literal["answered", "clarify", "no_data", "service_error"]
    confidence: float
    sources: list[SourceItem] = Field(default_factory=list)
    matched_question: str | None = None
    demo_mode: bool = False
    conversation_id: str
    authority: dict | None = None
    route_resolution: dict | None = None
    task_mode: Literal["information", "troubleshooting", "complaint", "safety", "benefit_help", "route_help", "unknown"] | None = None
    issue_type: str | None = None
    severity: str = "normal"
    dialogue_state: dict | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    demo_mode: bool
    knowledge_items: int
    rag_ready: bool = False
    rag_chunks: int = 0
    agent_ready: bool = False
    retrieval_mode: Literal["agentic_text_search", "unavailable"] = "unavailable"
