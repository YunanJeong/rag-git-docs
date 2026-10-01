"""진입점 3 — 검색을 MCP 서버로 띄운다. Claude Code 가 붙어 search_docs 를 부른다.

모델을 기동 때 한 번만 올려서 검색 한 번이 수십 ms 안에 끝난다.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from indexer import store
from indexer.embed import Embedder

embedder = Embedder()
db = store.client()
server = MCPServer(name="git-docs")


@server.tool()
def search_docs(query: str) -> str:
    """사내 git 리포의 문서에서 질문과 관련된 조각을 찾는다."""
    return "\n\n".join(store.search(db, embedder.encode([query])[0])) or "결과 없음"


if __name__ == "__main__":
    # 127.0.0.1 에만 연다. 인증이 없으므로 원격에서는 SSH 터널로 붙는다.
    server.run("streamable-http", host="127.0.0.1", port=8765)
