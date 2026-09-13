# Project state — 2026-09-13

## Stable architecture

- Production path: semantic-first `AgentAssistantService`.
- GigaChat function calling + deterministic local tools.
- Official text search with source-scope applicability.
- Responsibility Router and Route Resolver are deterministic.
- Safety uses `is_trip_ongoing` guard before `immediate_danger`/emergency tool.
- Concrete fact guard rejects unsupported numeric details.
- Tool/service-call markup cannot become `ChatResponse.answer`.
- Final JSON parser safely accepts only a complete object plus at most two unmatched trailing `}`; arbitrary trailing text/second object remains invalid.

## Automated tests

Clean repository regression suite: **48 passed, 0 failed** on 2026-09-13 with mocked GigaChat credentials.

## Live status before repository cleanup

Previous live acceptance after safety/fact guards: **5/6**. The only failure was malformed final JSON with an extra closing `}` in the payment scenario. The repository now contains a deterministic parser fix and regression tests for that exact protocol error. Full live 6-case acceptance still needs to be rerun against real GigaChat after deployment/configuration.

## Deployment notes

- Runtime: Python 3.12 + FastAPI/Uvicorn.
- Frontend: static HTML/CSS/JS served by FastAPI.
- Node.js: not required.
- Conversation state: in-memory; deploy one worker until external state storage is added.
- Secret `GIGACHAT_CREDENTIALS`: server `.env` only, never Git.
