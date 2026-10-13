import asyncio
import logging
import sys
from pathlib import Path

import pytest
from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
from cloner import code  # noqa: E402

USERS = {"t-kim": "kim", "t-lee": "lee"}


def test_parse_tokens():
    assert auth.parse_tokens(" kim:t-kim , lee:t-lee ") == USERS
    for bad in ["t-kim", "kim:", ":t-kim", "kim:t,lee:t", "kim:a,kim:b"]:
        with pytest.raises(ValueError) as e:
            auth.parse_tokens(bad)
        assert "t-kim" not in str(e.value), "오류 문구에 토큰이 나왔다"


def test_who():
    assert auth.who(USERS, b"Bearer t-lee") == "lee"
    assert auth.who(USERS, "Bearer t-kim") == "kim"
    assert auth.who(USERS, b"Bearer t-park") is None
    assert auth.who(USERS, b"t-kim") is None


def call(app, authorization: bytes | None) -> int:
    headers = [(b"authorization", authorization)] if authorization else []
    sent = []

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "headers": headers}
    asyncio.run(auth.require_token(inner, USERS)(scope, None, send))
    return sent[0]["status"]


def test_require_token():
    assert call(None, b"Bearer t-kim") == 200
    assert call(None, b"Bearer t-park") == 401
    assert call(None, None) == 401


def test_audited_keeps_tool_schema_and_logs_user(caplog):
    plain, wrapped = MCPServer(name="t"), MCPServer(name="t")
    plain.add_tool(code.read_code)
    wrapped.add_tool(auth.audited(code.read_code, USERS))
    [want] = asyncio.run(plain.list_tools())
    [got] = asyncio.run(wrapped.list_tools())
    assert got.model_dump() == want.model_dump(), "감싸면서 도구 이름·설명·스키마가 바뀌었다"

    class Ctx:
        headers = {"authorization": "Bearer t-lee"}

    logging.getLogger("rag.audit").setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="rag.audit"):
        out = auth.audited(lambda repo: f"ok {repo}", USERS)(repo="g/r", ctx=Ctx())
    assert out == "ok g/r"
    assert "lee" in caplog.text and "'repo': 'g/r'" in caplog.text
    assert "t-lee" not in caplog.text, "로그에 토큰이 나왔다"


def test_no_auth_refuses_to_listen_beyond_localhost():
    # 모델을 올리기 전에 끝나야 한다. 서버에 이 설정이 잘못 들어가도 인증 없이 열리지 않는다
    import os
    import subprocess

    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "AUTH_MODE": "none", "SERVE_HOST": "0.0.0.0", "COLLECT_MODE": "api"}
    r = subprocess.run([sys.executable, "serve.py"], cwd=root, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode != 0 and "SERVE_HOST=127.0.0.1" in r.stderr
