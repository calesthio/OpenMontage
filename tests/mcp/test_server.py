"""Contract tests for the read-only MCP tools and HTTP auth gate."""
import asyncio

from integrations.mcp_server import server


def test_list_pipelines(monkeypatch):
    monkeypatch.setattr(server, "list_pipelines", lambda: ["demo"])
    monkeypatch.setattr(server, "load_pipeline_readonly", lambda name: {
        "version": "1", "category": "generated",
        "stages": [{"name": "script"}, {"name": "compose"}],
    })
    result = server.om_list_pipelines()
    assert result["count"] == 1
    assert result["pipelines"][0]["stages"] == ["script", "compose"]


def test_estimate_unknown_pipeline(monkeypatch):
    monkeypatch.setattr(server, "list_pipelines", lambda: ["demo"])
    result = server.om_estimate_production("unknown")
    assert result["ok"] is False
    assert result["available_pipelines"] == ["demo"]


def test_estimate_declared_budget(monkeypatch):
    monkeypatch.setattr(server, "list_pipelines", lambda: ["demo"])
    monkeypatch.setattr(server, "load_pipeline_readonly", lambda name: {
        "orchestration": {"budget_default_usd": 2.5},
        "stages": [{"name": "script"}],
    })
    result = server.om_estimate_production("demo")
    assert result["ok"] is True
    assert result["declared_default_budget_usd"] == 2.5
    assert result["stage_count"] == 1


def test_http_auth_rejects_missing_token():
    async def scenario():
        sent = []
        async def app(scope, receive, send):
            raise AssertionError("unauthorized request reached MCP app")
        middleware = server.BearerTokenMiddleware(app, "x" * 40)
        async def send_fn(message):
            sent.append(message)
        await middleware(
            {"type": "http", "headers": []},
            lambda: None,
            send_fn,
        )
        assert sent[0]["status"] == 401
        assert b"unauthorized" in sent[1]["body"]
    asyncio.run(scenario())


def test_http_auth_accepts_correct_token():
    async def scenario():
        sent = []
        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})
        middleware = server.BearerTokenMiddleware(app, "x" * 40)
        async def send_fn(message):
            sent.append(message)
        await middleware(
            {"type": "http", "headers": [(b"authorization", b"Bearer " + b"x" * 40)]},
            lambda: None,
            send_fn,
        )
        assert sent[0]["status"] == 204
    asyncio.run(scenario())
