import time
import uuid

import httpx

from .config import Settings


class GigaChatError(RuntimeError):
    pass


class GigaChatClient:
    OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    API_BASE = "https://api.giga.chat"
    CHAT_URL = f"{API_BASE}/v1/chat/completions"
    MODELS_URL = f"{API_BASE}/v1/models"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._models_cache: list[dict] | None = None
        self._resolved_chat_model: str | None = None

    def _credentials(self) -> str:
        value = self.settings.gigachat_credentials.strip()
        lowered = value.lower()
        if lowered.startswith("basic "):
            value = value[6:].strip()
        elif lowered.startswith("bearer "):
            value = value[7:].strip()
        return value

    async def _access_token(self, force_refresh: bool = False) -> str:
        now = time.time()
        if not force_refresh and self._token and now < self._token_expires_at - 60:
            return self._token

        credentials = self._credentials()
        if not credentials:
            raise GigaChatError("GIGACHAT_CREDENTIALS is empty")

        headers = {
            "Authorization": f"Basic {credentials}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"scope": self.settings.gigachat_scope}

        try:
            async with httpx.AsyncClient(
                verify=self.settings.gigachat_verify_ssl,
                timeout=30,
                follow_redirects=True,
                trust_env=False,
            ) as client:
                response = await client.post(self.OAUTH_URL, headers=headers, data=data)
        except httpx.HTTPError as exc:
            raise GigaChatError(
                f"OAuth network error: endpoint={self.OAUTH_URL}; {type(exc).__name__}: {exc}"
            ) from exc

        if response.is_error:
            detail = response.text[:500].replace("\n", " ")
            raise GigaChatError(f"OAuth failed: HTTP {response.status_code}: {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise GigaChatError("OAuth returned invalid JSON") from exc

        token = payload.get("access_token")
        if not token:
            raise GigaChatError("OAuth response does not contain access_token")

        expires_at = payload.get("expires_at")
        if isinstance(expires_at, (int, float)):
            if expires_at > 10_000_000_000:
                expires_at = expires_at / 1000
            self._token_expires_at = float(expires_at)
        else:
            self._token_expires_at = now + 29 * 60

        self._token = token
        return token

    async def _request(self, method: str, url: str, *, json: dict | None = None, timeout: int = 45) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(2):
            token = await self._access_token(force_refresh=attempt == 1)
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
            if json is not None:
                headers["Content-Type"] = "application/json"
            try:
                async with httpx.AsyncClient(
                    verify=self.settings.gigachat_verify_ssl,
                    timeout=timeout,
                    follow_redirects=True,
                    trust_env=False,
                ) as client:
                    response = await client.request(method, url, headers=headers, json=json)
            except httpx.HTTPError as exc:
                last_error = exc
                break

            if response.status_code == 401 and attempt == 0:
                self._token = None
                self._token_expires_at = 0
                continue
            return response

        if last_error:
            raise GigaChatError(
                f"GigaChat network error: endpoint={url}; {type(last_error).__name__}: {last_error}"
            ) from last_error
        raise GigaChatError("GigaChat request failed after token refresh")

    async def models(self, refresh: bool = False) -> list[dict]:
        if self._models_cache is not None and not refresh:
            return self._models_cache
        response = await self._request("GET", self.MODELS_URL, timeout=30)
        if response.is_error:
            detail = response.text[:500].replace("\n", " ")
            raise GigaChatError(f"Models failed: HTTP {response.status_code}: {detail}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise GigaChatError("Models endpoint returned invalid JSON") from exc
        self._models_cache = payload.get("data", [])
        return self._models_cache

    async def _chat_model(self) -> str:
        if self._resolved_chat_model:
            return self._resolved_chat_model

        requested = self.settings.gigachat_model.strip()
        try:
            models = await self.models()
        except GigaChatError:
            raise

        ids = [str(row.get("id", "")) for row in models if row.get("id")]
        if requested in ids:
            self._resolved_chat_model = requested
            return requested

        preferred = ["GigaChat-3-Ultra", "GigaChat-2-Pro", "GigaChat-2-Max", "GigaChat-2-Lite"]
        for candidate in preferred:
            if candidate in ids:
                self._resolved_chat_model = candidate
                return candidate

        chat_models = [
            str(row.get("id"))
            for row in models
            if row.get("id") and (row.get("type") in (None, "chat")) and "Embedding" not in str(row.get("id"))
        ]
        if chat_models:
            self._resolved_chat_model = chat_models[0]
            return chat_models[0]

        self._resolved_chat_model = requested
        return requested

    async def chat_completion(
        self,
        messages: list[dict],
        functions: list[dict] | None = None,
        function_call: str | dict = "auto",
    ) -> dict:
        payload = {
            "model": await self._chat_model(),
            "messages": messages,
            "temperature": 0.12,
            "max_tokens": 1200,
        }
        if functions:
            payload["functions"] = functions
            payload["function_call"] = function_call
        elif function_call == "none":
            payload["function_call"] = "none"
        response = await self._request("POST", self.CHAT_URL, json=payload, timeout=90)
        if response.is_error:
            detail = response.text[:500].replace("\n", " ")
            raise GigaChatError(f"Chat failed: HTTP {response.status_code}: {detail}")
        try:
            choice = response.json()["choices"][0]
            return {"message": choice["message"], "finish_reason": choice.get("finish_reason")}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise GigaChatError("Chat endpoint returned an unexpected response") from exc

    async def diagnose(self) -> dict:
        result = {
            "credentials_configured": bool(self._credentials()),
            "scope": self.settings.gigachat_scope,
            "selected_chat_model": self.settings.gigachat_model,
            "gigachat_embeddings": {"available": False, "reason": "payment_required"},
            "oauth_ok": False,
            "models_ok": False,
            "chat_ok": False,
            "agent": {"ready": False},
            "error": None,
        }
        if not result["credentials_configured"]:
            result["error"] = "GIGACHAT_CREDENTIALS is empty"
            return result
        try:
            await self._access_token(force_refresh=True)
            result["oauth_ok"] = True
            models = await self.models(refresh=True)
            result["models_ok"] = True
            result["available_models"] = [row.get("id") for row in models if row.get("id")]
            result["selected_chat_model"] = await self._chat_model()
            # A model listed by /models may still be unavailable because of quota.
            probe = await self.chat_completion([{"role": "user", "content": "Ответь одним словом: работает?"}], None)
            result["chat_ok"] = bool(probe.get("message", {}).get("content"))
            function_probe = await self.chat_completion(
                [{"role": "user", "content": "Для проверки обязательно вызови функцию health_check."}],
                [{"name": "health_check", "description": "Техническая проверка function calling", "parameters": {"type": "object", "properties": {}}}],
                "auto",
            )
            function_ready = bool(function_probe.get("message", {}).get("function_call", {}).get("name") == "health_check")
            result["function_calling"] = {"ready": function_ready}
            result["agent"] = {"ready": bool(result["chat_ok"] and function_ready)}
        except GigaChatError as exc:
            result["error"] = str(exc)
        return result
