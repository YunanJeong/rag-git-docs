"""진입점 3 — 검색을 MCP 서버로 띄운다. Claude Code 가 붙어 search_docs 를 부른다.

질문도 문서 조각과 같은 모델(bge-m3)로 벡터로 바꿔야 비교가 된다. 그래서 색인에 쓴
indexer.embed 를 여기서도 쓴다. 모델은 기동 때 한 번만 올려 검색 한 번이 수십 ms 안에 끝난다.

네트워크에 열리므로 모든 요청에 Authorization: Bearer <SERVE_TOKEN> 을 요구한다.
"""

from __future__ import annotations

import hmac
import os
import sys

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from qdrant_client import models

from indexer import store
from indexer.embed import Embedder

embedder = Embedder()
db = store.client()
server = MCPServer(name="git-docs")


@server.tool()
def search_docs(query: str) -> str:
    """사내 git 리포의 문서에서 질문과 관련된 조각을 찾는다."""
    vector = embedder.encode([query])[0]
    hits = db.query_points(
        store.ALIAS,
        prefetch=[
            models.Prefetch(query=vector["dense"], using="dense", limit=20),
            models.Prefetch(query=vector["sparse"], using="sparse", limit=20),
        ],
        # 뜻으로 찾은 결과(dense)와 글자로 찾은 결과(sparse)의 순위를 합친다
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=5,
    ).points
    return "\n\n".join(h.payload["text"] for h in hits) or "결과 없음"


def require_token(app, token: str):
    """검색 서버 토큰이 맞지 않는 요청은 MCP 서버에 닿기 전에 401 로 돌려보낸다."""
    expected = f"Bearer {token}".encode()

    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            got = dict(scope["headers"]).get(b"authorization", b"")
            # 응답 시간 차이로 토큰을 한 글자씩 알아내지 못하게 고정 시간으로 비교한다
            if not hmac.compare_digest(got, expected):
                await send({"type": "http.response.start", "status": 401, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
        await app(scope, receive, send)

    return guarded


if __name__ == "__main__":
    token = os.environ.get("SERVE_TOKEN")
    if not token:
        # 검색 서버 토큰 없이 네트워크에 열리는 일이 없도록 아예 뜨지 않는다
        sys.exit("SERVE_TOKEN 이 필요하다")
    # SDK 는 127.0.0.1 로 들어온 요청만 통과시키는 Host 헤더 검사를 켜 둔다.
    # Service 를 거쳐 노드 IP 로 들어오는 요청이 막히지 않게 끄고, 검색 서버 토큰으로 막는다.
    app = server.streamable_http_app(
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    uvicorn.run(
        require_token(app, token),
        host=os.environ.get("SERVE_HOST", "0.0.0.0"),
        port=8765,
        log_level="warning",
    )
