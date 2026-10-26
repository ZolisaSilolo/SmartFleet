"""
Amazon Bedrock access. There is NO offline/heuristic fallback: if the model is unavailable the API says so
(503) and the caller sees an honest error. Operators can switch AI off with AI_ENABLED=false (kill switch).
"""
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from shared.errors import ApiError
from shared.observability import logger, metrics

_client = None


def ai_enabled() -> bool:
    return os.environ.get("AI_ENABLED", "true").strip().lower() == "true"


def require_ai() -> None:
    if not ai_enabled():
        raise ApiError(503, "AI_DISABLED", "AI features are currently disabled by the operator.")


def model_id() -> str:
    return os.environ["BEDROCK_MODEL_ID"]


def supports_temperature() -> bool:
    """Reasoning models (e.g. Moonshot Kimi) reject the temperature field; default off."""
    return os.environ.get("BEDROCK_SUPPORTS_TEMPERATURE", "false").strip().lower() == "true"


def inference_config(max_tokens: int, temperature: float = 0.2) -> dict:
    cfg = {"maxTokens": max_tokens}
    if supports_temperature():
        cfg["temperature"] = temperature
    return cfg


def extract_text(message: dict) -> str:
    """Concatenate text blocks, ignoring reasoningContent blocks some models emit before the answer."""
    return "".join(block.get("text", "") for block in message.get("content", [])).strip()


def client_config() -> Config:
    return Config(connect_timeout=5, read_timeout=int(os.environ.get("BEDROCK_READ_TIMEOUT_SECONDS", "20")),
                  retries={"max_attempts": 2, "mode": "standard"})


def get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"), config=client_config())
    return _client


def converse_text(system: str, user: str, max_tokens: int = 2048, temperature: float = 0.2) -> str:
    require_ai()
    metrics.add_metric(name="AiRequests", unit="Count", value=1)
    try:
        resp = get_client().converse(
            modelId=model_id(),
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig=inference_config(max_tokens, temperature),
        )
        return extract_text(resp["output"]["message"])
    except (ClientError, BotoCoreError) as exc:
        metrics.add_metric(name="AiFailures", unit="Count", value=1)
        code = exc.response.get("Error", {}).get("Code") if isinstance(exc, ClientError) else type(exc).__name__
        logger.error("bedrock_invocation_failed", extra={"error_code": code})
        raise ApiError(503, "AI_UNAVAILABLE", "The AI service is temporarily unavailable. Please retry shortly.") from exc
