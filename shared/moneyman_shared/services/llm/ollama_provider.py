import httpx

from moneyman_shared.config import get_settings
from moneyman_shared.services.llm.base import ClassificationResult, ExtractionResult
from moneyman_shared.services.llm.tools import (
    CLASSIFICATION_SYSTEM_PROMPT,
    CLASSIFY_TOOL,
    EXTRACT_TOOL,
    EXTRACTION_SYSTEM_PROMPT,
)


def _as_ollama_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }


class OllamaProvider:
    """Talks to a local Ollama server (https://ollama.com) via its OpenAI-style tool-calling API.

    Requires `ollama serve` running locally and the configured model pulled
    (e.g. `ollama pull llama3.1:8b`). Tool-call reliability is model-dependent —
    smaller local models refuse or malform tool calls more often than Claude.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_MODEL

    def _call_tool_once(self, system: str, user_content: str, tool: dict, tool_name: str) -> dict | None:
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                "tools": [_as_ollama_tool(tool)],
                "stream": False,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()

        for tool_call in data.get("message", {}).get("tool_calls", []) or []:
            function = tool_call.get("function", {})
            if function.get("name") == tool_name:
                return function.get("arguments") or {}

        return None

    def _call_tool(self, system: str, user_content: str, tool: dict, tool_name: str) -> dict | None:
        # Small local models occasionally skip the tool call on the first try;
        # one retry cuts the miss rate substantially without masking real failures.
        for _ in range(2):
            data = self._call_tool_once(system, user_content, tool, tool_name)
            if data is not None:
                return data
        return None

    def classify_email(
        self, subject: str | None, sender: str | None, snippet: str | None
    ) -> ClassificationResult:
        user_content = f"Sender: {sender or ''}\nSubject: {subject or ''}\nSnippet: {snippet or ''}"

        data = self._call_tool(
            CLASSIFICATION_SYSTEM_PROMPT, user_content, CLASSIFY_TOOL, "classify_transaction_email"
        )
        if data is None:
            return ClassificationResult(is_transaction_email=False, confidence=0.0, reason="no tool call returned")

        return ClassificationResult(
            is_transaction_email=bool(data.get("is_transaction_email", False)),
            confidence=float(data.get("confidence", 0.0)),
            reason=str(data.get("reason", "")),
        )

    def extract_transaction(
        self, subject: str | None, sender: str | None, body_text: str | None
    ) -> ExtractionResult:
        user_content = f"Sender: {sender or ''}\nSubject: {subject or ''}\nBody:\n{body_text or ''}"

        data = self._call_tool(EXTRACTION_SYSTEM_PROMPT, user_content, EXTRACT_TOOL, "extract_transaction")
        if data is None:
            return ExtractionResult(
                is_transaction=False,
                amount=None,
                currency=None,
                txn_type=None,
                merchant_or_counterparty=None,
                txn_date=None,
                account_last4=None,
                issuer_or_bank_name=None,
                account_type=None,
                category_hint=None,
                confidence=0.0,
                ambiguity_notes="no tool call returned",
                raw={},
            )

        return ExtractionResult(
            is_transaction=bool(data.get("is_transaction", False)),
            amount=data.get("amount"),
            currency=data.get("currency"),
            txn_type=data.get("txn_type"),
            merchant_or_counterparty=data.get("merchant_or_counterparty"),
            txn_date=data.get("txn_date"),
            account_last4=data.get("account_last4"),
            issuer_or_bank_name=data.get("issuer_or_bank_name"),
            account_type=data.get("account_type"),
            category_hint=data.get("category_hint"),
            confidence=float(data.get("confidence", 0.0)),
            ambiguity_notes=data.get("ambiguity_notes"),
            raw=data,
        )
