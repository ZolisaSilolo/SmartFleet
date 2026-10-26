import json
from datetime import UTC, datetime

import pytest
import shared.bedrock as bedrock
from botocore.exceptions import ClientError
from conftest import call, make_driver, make_vehicle

INSIGHTS = [
    {"title": "Cut idling", "recommendation": "Reduce idling.", "estimatedSavingZar": "R 1,000 - R 2,000 / month", "priority": "HIGH"},
    {"title": "Service on time", "recommendation": "Schedule service.", "estimatedSavingZar": "R 500", "priority": "MEDIUM"},
    {"title": "Invoice faster", "recommendation": "Invoice on delivery.", "estimatedSavingZar": "R 3,000 liquidity", "priority": "LOW"},
]


class FakeBedrock:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"output": {"message": {"content": [{"text": self.text}]}}}


def use_bedrock(monkeypatch, **kwargs):
    fake = FakeBedrock(**kwargs)
    monkeypatch.setattr(bedrock, "_client", fake)
    return fake


def throttled():
    return ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "Converse")


def test_insights_use_the_model_and_only_send_aggregates(ai_h, vehicles_h, drivers_h, monkeypatch):
    fake = use_bedrock(monkeypatch, text="Here you go:\n```json\n" + json.dumps(INSIGHTS) + "\n```")
    make_vehicle(vehicles_h, plate="CA SECRET-1")
    make_driver(drivers_h)
    status, body = call(ai_h, "POST", "/analytics/ai-insights")
    assert status == 200 and len(body["insights"]) == 3 and body["model"] == "global.test-model"
    sent = json.dumps(fake.calls[0])
    assert "CA SECRET-1" not in sent and "Sipho" not in sent and "+27821234567" not in sent   # data minimisation
    assert fake.calls[0]["modelId"] == "global.test-model"


@pytest.mark.parametrize("text", ["I cannot do that", "[]", json.dumps(INSIGHTS[:2]), json.dumps([{"title": "x"}] * 3), "[not json]"])
def test_bad_model_output_is_an_error_not_a_made_up_answer(ai_h, monkeypatch, text):
    use_bedrock(monkeypatch, text=text)
    status, body = call(ai_h, "POST", "/analytics/ai-insights")
    assert status == 502 and body["error"]["code"] == "AI_BAD_RESPONSE" and "insights" not in body


def test_bedrock_outage_returns_503_with_no_heuristic_fallback(ai_h, monkeypatch):
    use_bedrock(monkeypatch, error=throttled())
    status, body = call(ai_h, "POST", "/analytics/ai-insights")
    assert status == 503 and body["error"]["code"] == "AI_UNAVAILABLE" and "insights" not in body


def test_kill_switch_blocks_all_ai_endpoints(ai_h, monkeypatch):
    fake = use_bedrock(monkeypatch, text=json.dumps(INSIGHTS))
    monkeypatch.setenv("AI_ENABLED", "false")
    assert call(ai_h, "POST", "/analytics/ai-insights")[1]["error"]["code"] == "AI_DISABLED"
    assert call(ai_h, "POST", "/agent/chat", body={"message": "hi"})[0] == 503
    assert fake.calls == []


def test_rate_limit_is_per_tenant_and_returns_retry_after(ai_h, monkeypatch):
    use_bedrock(monkeypatch, text=json.dumps(INSIGHTS))
    for _ in range(3):
        assert call(ai_h, "POST", "/analytics/ai-insights")[0] == 200
    status, body = call(ai_h, "POST", "/analytics/ai-insights")
    assert status == 429 and body["error"]["code"] == "RATE_LIMITED"
    assert call(ai_h, "POST", "/analytics/ai-insights", tenant="tenant-b")[0] == 200   # other tenants unaffected


def test_rate_limiter_fails_closed_when_it_cannot_meter(ai_h, monkeypatch):
    import shared.ratelimit as ratelimit
    use_bedrock(monkeypatch, text=json.dumps(INSIGHTS))

    def broken_table(_name):
        class T:
            def update_item(self, **kw):
                raise ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "UpdateItem")
        return T()
    monkeypatch.setattr(ratelimit, "get_table", broken_table)
    assert call(ai_h, "POST", "/analytics/ai-insights")[1]["error"]["code"] == "RATE_LIMITER_UNAVAILABLE"


def test_agent_chat_validates_input_and_maps_failures(ai_h, monkeypatch):
    import agent.fleet_agent as fleet_agent
    assert call(ai_h, "POST", "/agent/chat", body={})[0] == 400
    assert call(ai_h, "POST", "/agent/chat", body={"message": "x" * 2001})[0] == 400
    assert call(ai_h, "POST", "/agent/chat", body={"message": "hi", "tenantId": "tenant-b"})[0] == 400

    monkeypatch.setattr(fleet_agent, "_run", lambda m, t: {"response": f"ok for {t}", "engine": "STRANDS_BEDROCK", "model": "m", "toolExecutions": []})
    status, body = call(ai_h, "POST", "/agent/chat", tenant="tenant-a", body={"message": "How is my cash flow?"})
    assert status == 200 and body["response"] == "ok for tenant-a"      # tenant comes from the token, never the body

    def fail_bedrock(m, t):
        raise throttled()
    monkeypatch.setattr(fleet_agent, "_run", fail_bedrock)
    assert call(ai_h, "POST", "/agent/chat", body={"message": "hi"})[1]["error"]["code"] == "AI_UNAVAILABLE"

    def fail_other(m, t):
        raise RuntimeError("tool exploded")
    monkeypatch.setattr(fleet_agent, "_run", fail_other)
    assert call(ai_h, "POST", "/agent/chat", body={"message": "hi"})[0] == 502


def test_agent_timeout_is_reported(monkeypatch):
    import time

    import agent.fleet_agent as fleet_agent
    from shared.errors import ApiError
    monkeypatch.setattr(fleet_agent, "_run", lambda m, t: time.sleep(1.0))
    with pytest.raises(ApiError) as exc:
        fleet_agent.execute_agent_command("slow", "tenant-a", timeout_seconds=0.05)
    assert exc.value.status_code == 504


# ---- agent tools (called directly; each tool is bound to ONE tenant) ----------------------------------------------
def tools_for(tenant):
    from agent.fleet_agent import build_tools
    return {t.tool_name: t for t in build_tools(tenant)}


def test_tools_only_see_their_own_tenant(vehicles_h, stations_h):
    make_vehicle(vehicles_h, tenant="tenant-a")
    kpis_a = tools_for("tenant-a")["get_fleet_financial_kpis"]()
    kpis_b = tools_for("tenant-b")["get_fleet_financial_kpis"]()
    assert kpis_a["totalVehicles"] == 1 and kpis_b["totalVehicles"] == 0
    assert tools_for("tenant-a")["audit_fuel_geofences"]()["status"] == "NO_STATIONS_CONFIGURED"


def test_propose_maintenance_creates_a_proposal_only(vehicles_h, maint_h):
    v = make_vehicle(vehicles_h, odometer=5000)
    result = tools_for("tenant-a")["propose_maintenance_service"](v["vehicleId"], "BRAKES", "Pads worn", 3500.0)
    assert result["status"] == "PROPOSED" and "NOT been booked" in result["note"]
    rec = call(maint_h, "GET", f"/maintenance/{result['recordId']}")[1]
    assert rec["status"] == "PROPOSED" and rec["odometerAtServiceKm"] == 5000 and rec["description"].startswith("[AI proposal]")
    assert call(vehicles_h, "GET", f"/vehicles/{v['vehicleId']}")[1]["status"] == "ACTIVE"      # vehicle untouched
    due = call(maint_h, "GET", "/maintenance/due")[1]["items"]
    assert due == []                                                                           # proposals are not "due" work


def test_propose_maintenance_is_validated_and_tenant_bound(vehicles_h):
    from shared.errors import ApiError
    v = make_vehicle(vehicles_h, tenant="tenant-a")
    propose = tools_for("tenant-a")["propose_maintenance_service"]
    with pytest.raises(ValueError):
        propose(v["vehicleId"], "WASH_AND_WAX", "nonsense", 10.0)
    with pytest.raises(ValueError):
        propose(v["vehicleId"], "BRAKES", "Pads", 9_999_999.0)
    with pytest.raises(ApiError):
        propose("does-not-exist", "BRAKES", "Pads", 100.0)
    with pytest.raises(ApiError):
        tools_for("tenant-b")["propose_maintenance_service"](v["vehicleId"], "BRAKES", "Pads", 100.0)   # not tenant-b's vehicle


def test_geofence_audit_tool_flags_off_station_fills(vehicles_h, stations_h, fuel_h):
    v = make_vehicle(vehicles_h)
    call(stations_h, "POST", "/stations", body={"name": "Shell", "latitude": -28.2713, "longitude": 29.1352, "radiusKm": 1})
    for lat, lon in [(-28.2713, 29.1352), (-28.75, 28.84)]:
        call(fuel_h, "POST", "/fuel", body={"vehicleId": v["vehicleId"], "fillDate": datetime.now(UTC).isoformat(), "litres": 40,
                                             "totalCostZar": 800, "odometerKm": 1000, "latitude": lat, "longitude": lon})
    audit = tools_for("tenant-a")["audit_fuel_geofences"]()
    assert audit["fillUpsChecked"] == 2 and audit["flaggedCount"] == 1 and audit["flagged"][0]["status"] == "OUTSIDE_AUTHORIZED"
