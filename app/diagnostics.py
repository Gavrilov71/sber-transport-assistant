import asyncio
import json
import sys
from pathlib import Path

from .config import get_settings
from .gigachat_client import GigaChatClient
from .text_search import OfficialTextSearch


async def main() -> None:
    settings = get_settings()
    search = OfficialTextSearch(settings)
    result = await GigaChatClient(settings).diagnose()
    snapshots = []
    if settings.source_snapshots_path.exists():
        try:
            snapshots = json.loads(settings.source_snapshots_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            snapshots = []
    snapshots_ready = bool(snapshots) and all(
        row.get("http_status") == 200 and Path(row.get("raw_file", "")).exists()
        for row in snapshots
    )
    result.update({
        "rag_chunks": len(search.chunks),
        "source_snapshots_ready": snapshots_ready,
        "sources_count": len(__import__("json").loads(settings.sources_path.read_text(encoding="utf-8"))),
        "retrieval": {"mode": "agentic_text_search", "ready": search.ready},
        "agent": {"ready": bool(result.get("chat_ok") and result.get("function_calling", {}).get("ready") and search.ready)},
        "embeddings_dependency": "none",
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))
    required = ("oauth_ok", "models_ok", "chat_ok")
    if not all(result.get(key) for key in required):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
