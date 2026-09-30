"""진입점 3 — 검색을 MCP 서버로 띄운다.

모델을 기동 때 한 번만 올려 두므로 질의 한 번이 임베딩 한 번과 Qdrant 조회 한 번이다.
팀원의 Claude Code 가 네트워크로 붙고, 요청마다 Bearer 토큰을 확인한다.
"""

from __future__ import annotations

import hmac
import os
import sys

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from vectordb.embed import Embedder
from vectordb.store import Store

embedder = Embedder()
store = Store()
server = MCPServer(
    name="git-docs",
    instructions="사내 git 리포의 문서를 찾는다. 문서로 남아 있을 만한 질문이면 답하기 전에 "
    "search_docs 를 부르고, 답에 근거로 쓴 doc_path 를 적는다.",
)


@server.tool()
def search_docs(query: str, top_k: int = 5) -> str:
    """사내 문서에서 질문과 관련된 조각을 찾는다. 식별자나 에러 코드도 그대로 넣으면 된다."""
    dense, sparse = embedder.encode([query])
    hits = store.search(dense[0], sparse[0], top_k=max(1, min(top_k, 20)))
    return "\n\n".join(f"[{i}] {h.text}" for i, h in enumerate(hits, 1)) or "결과 없음"


def _require_token(app, token: str):
    """모든 요청에 Authorization: Bearer <token> 을 요구한다. 팀이 토큰 하나를 나눠 쓴다."""
    expected = f"Bearer {token}".encode()

    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            got = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(got, expected):
                await send({"type": "http.response.start", "status": 401, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
        await app(scope, receive, send)

    return guarded


def main() -> int:
    token = os.environ.get("SERVE_TOKEN")
    if not token:
        print("SERVE_TOKEN 이 필요하다. openssl rand -hex 32 로 만든다", file=sys.stderr)
        return 2
    print(f"색인 {store.alias}: 조각 {store.count()}개. 모델 로딩", file=sys.stderr)
    embedder.load()

    # SDK 의 Host 헤더 검사는 127.0.0.1 로 붙는 경우만 허용한다.
    # 팀원은 IP 나 호스트 이름으로 붙으므로 검사를 끄고 토큰으로 막는다.
    app = server.streamable_http_app(
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    port = int(os.environ.get("SERVE_PORT", "8765"))
    uvicorn.run(_require_token(app, token), host="0.0.0.0", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
