"""검색 서버의 사용자별 토큰. SERVE_TOKEN 의 '이름:토큰,이름:토큰' 으로 누가 부르는지 가리고 도구 호출을 남긴다."""

from __future__ import annotations

import functools
import hmac
import inspect
import logging

from mcp.server.mcpserver import Context

log = logging.getLogger("rag.audit")


def parse_tokens(raw: str) -> dict[str, str]:
    """'이름:토큰' 을 쉼표로 이은 값을 {토큰: 이름} 으로 바꾼다. 오류 문구에 토큰은 넣지 않는다."""
    users: dict[str, str] = {}
    for entry in raw.split(","):
        name, sep, token = entry.strip().partition(":")
        if not (sep and name and token):
            raise ValueError("SERVE_TOKEN 은 '이름:토큰' 을 쉼표로 잇는다")
        if token in users or name in users.values():
            raise ValueError(f"SERVE_TOKEN 에 겹치는 이름이나 토큰이 있다: {name}")
        users[token] = name
    return users


def who(users: dict[str, str], authorization: str | bytes) -> str | None:
    """Authorization 헤더의 주인 이름. 응답 시간으로 토큰을 알아내지 못하게 모든 토큰과 고정 시간으로 비교한다."""
    got = authorization.encode() if isinstance(authorization, str) else authorization
    found = None
    for token, name in users.items():
        if hmac.compare_digest(got, f"Bearer {token}".encode()):
            found = name
    return found


def require_token(app, users: dict[str, str]):
    """등록된 토큰이 아닌 요청은 MCP 서버에 닿기 전에 401 로 돌려보낸다."""

    async def guarded(scope, receive, send):
        if scope["type"] == "http" and who(users, dict(scope["headers"]).get(b"authorization", b"")) is None:
            await send({"type": "http.response.start", "status": 401, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        await app(scope, receive, send)

    return guarded


def audited(fn, users: dict[str, str]):
    """도구를 감싸, 부를 때마다 '이름 도구 인자' 를 한 줄 남긴다. 도구 이름·설명·인자 스키마는 원래 함수 그대로다."""
    sig = inspect.signature(fn, eval_str=True)

    @functools.wraps(fn)
    def run(*args, ctx: Context, **kwargs):
        headers = ctx.headers or {}
        log.info("%s %s %s", who(users, headers.get("authorization", "")) or "-", fn.__name__, kwargs)
        return fn(*args, **kwargs)

    # SDK 는 Context 로 표시된 인자에 요청 정보를 넣어 주고, 그 인자는 도구 스키마에서 뺀다
    ctx_param = inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context)
    run.__signature__ = sig.replace(parameters=[*sig.parameters.values(), ctx_param])
    run.__annotations__ = {
        **{p.name: p.annotation for p in sig.parameters.values()},
        "ctx": Context,
        "return": sig.return_annotation,
    }
    return run
