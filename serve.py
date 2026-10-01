"""진입점 3 — 검색을 MCP 서버로 띄운다. Claude Code 가 붙어 search_docs 를 부른다.

질문도 문서 조각과 같은 모델(bge-m3)로 벡터로 바꿔야 비교가 된다. 그래서 색인에 쓴
indexer.embed 를 여기서도 쓴다. 모델은 기동 때 한 번만 올려 검색 한 번이 수십 ms 안에 끝난다.
"""

from __future__ import annotations

import os

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


if __name__ == "__main__":
    # 인증이 없으므로 기본은 127.0.0.1 이다. 파드 안에서는 0.0.0.0 으로 받고,
    # 바깥에는 열지 않은 채 kubectl port-forward 로 붙는다.
    # SDK 의 Host 헤더 검사는 127.0.0.1 로 붙는 요청만 통과시켜서, 0.0.0.0 일 때는 끈다.
    host = os.environ.get("SERVE_HOST", "127.0.0.1")
    security = None if host == "127.0.0.1" else TransportSecuritySettings(enable_dns_rebinding_protection=False)
    server.run("streamable-http", host=host, port=8765, transport_security=security)
