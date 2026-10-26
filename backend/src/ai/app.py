"""AI endpoints: cash-flow insights and the autonomous agent. Isolated Lambda = scoped Bedrock IAM + blast radius."""
import json
from typing import List, Literal

from agent.fleet_agent import execute_agent_command
from pydantic import BaseModel, Field, ValidationError
from shared import bedrock
from shared.errors import ApiError
from shared.fleet_data import load_fleet
from shared.fleet_metrics import compute_dashboard
from shared.http import create_app, make_handler, parse_body, tenant
from shared.ratelimit import check_rate_limit
from shared.response import ok
from shared.utils import current_iso_time
from shared.validation import RequestModel

app = create_app()

MAX_MESSAGE_CHARS = 2000


class ChatRequest(RequestModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)


class Insight(BaseModel):
    title: str = Field(..., max_length=140)
    recommendation: str = Field(..., max_length=700)
    estimatedSavingZar: str = Field(..., max_length=100)
    priority: Literal["HIGH", "MEDIUM", "LOW"]


INSIGHT_SYSTEM = (
    "You are a financial analyst for South African transport SMEs. Reply with ONLY a JSON array of exactly 3 objects "
    'with keys "title", "recommendation", "estimatedSavingZar" (a short text range in ZAR) and "priority" (HIGH|MEDIUM|LOW). '
    "Base every recommendation strictly on the metrics provided; do not assume facts that are not given."
)


def parse_insights(text: str) -> List[Insight]:
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ApiError(502, "AI_BAD_RESPONSE", "The AI response was not in the expected format.")
    try:
        items = [Insight(**i) for i in json.loads(text[start : end + 1])]
    except (ValueError, TypeError, ValidationError) as exc:
        raise ApiError(502, "AI_BAD_RESPONSE", "The AI response was not in the expected format.") from exc
    if len(items) != 3:
        raise ApiError(502, "AI_BAD_RESPONSE", "The AI response was not in the expected format.")
    return items


@app.post("/analytics/ai-insights")
def ai_insights():
    tenant_id = tenant(app)
    bedrock.require_ai()
    check_rate_limit(tenant_id, "insights")
    data = load_fleet(tenant_id)
    d = compute_dashboard(data)
    completed = sum(1 for t in data.trips if t.get("status") == "COMPLETED")
    prompt = (
        f"Fleet metrics (aggregates only, ZAR):\n- Vehicles: {d['totalVehiclesCount']} ({d['activeVehiclesCount']} active)\n"
        f"- Completed trips in the last {data.window_days} days: {completed}\n- MTD revenue: {d['mtdRevenueZar']:.2f}\n"
        f"- MTD fuel spend: {d['mtdFuelSpendZar']:.2f}\n- MTD maintenance spend: {d['mtdMaintenanceSpendZar']:.2f}\n"
        f"- Net operational cash flow MTD: {d['netOperationalCashFlowZar']:.2f}\n- Overdue maintenance items: {d['overdueMaintenanceCount']}"
    )
    insights = parse_insights(bedrock.converse_text(INSIGHT_SYSTEM, prompt, max_tokens=2048))
    return ok({"insights": [i.model_dump() for i in insights], "generatedAt": current_iso_time(), "model": bedrock.model_id(),
               "disclaimer": "AI-generated estimates; verify before acting."})


@app.post("/agent/chat")
def agent_chat():
    tenant_id = tenant(app)
    bedrock.require_ai()
    req = parse_body(app, ChatRequest)
    check_rate_limit(tenant_id, "agent")
    remaining_ms = app.lambda_context.get_remaining_time_in_millis() if app.lambda_context else 25000
    return ok(execute_agent_command(req.message, tenant_id, timeout_seconds=max(5.0, remaining_ms / 1000.0 - 3.0)))


lambda_handler = make_handler(app)
