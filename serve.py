"""진입점 3 — 검색을 MCP 서버로 띄운다. Claude Code 가 붙어 search_docs 를 부른다.

질문도 문서 조각과 같은 모델(bge-m3)로 벡터로 바꿔야 비교가 된다. 그래서 색인에 쓴
indexer.embed 를 여기서도 쓴다. 모델은 기동 때 한 번만 올려 검색 한 번이 수십 ms 안에 끝난다.

네트워크에 열리므로 모든 요청에 Authorization: Bearer <SERVE_TOKEN> 을 요구한다.

COLLECT_MODE=clone 이면 DOCS_DIR 의 clone 을 읽는 코드 도구(search_code, read_code)를 함께 노출한다.
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

MODE = os.environ.get("COLLECT_MODE", "api")
if MODE not in ("api", "clone"):
    sys.exit(f"COLLECT_MODE 는 api 또는 clone 이다: {MODE}")
if MODE == "clone" and not os.environ.get("DOCS_DIR"):
    sys.exit("COLLECT_MODE=clone 이면 clone 이 있는 DOCS_DIR 이 필요하다")

embedder = Embedder()
db = store.client()
# 서버 사용 지침. Claude Code 가 세션에 넣어 주어, 언제 검색하고 결과를 어떻게 쓸지 정한다.
INSTRUCTIONS = """\
팀 내부 지식 검색 서버다. 사내 GitLab 리포들의 README·운영 문서·배포 절차·설계 기록이 색인돼 있다.

다음 질문이면 답하기 전에 search_docs 를 먼저 부른다.
- 사내 프로젝트, 서비스, 리포 이름이 나오는 질문
- 우리 팀이 어떻게 하는지 묻는 질문 (배포·롤백·설정·장애 대응·운영 규칙)
- 일반 지식으로 답할 수 있어도, 팀의 실제 방식이 다를 수 있는 질문

결과에는 문서 경로와 마지막 수정일이 붙어 있다. 답할 때 근거로 쓴 문서 경로를 적고,
수정일이 오래된 문서는 지금과 다를 수 있다고 알린다. 찾지 못하면 찾지 못했다고 말하고 추측하지 않는다.
"""
CODE_INSTRUCTIONS = """
같은 리포들의 코드도 볼 수 있다. 문서 검색을 먼저 하고, 문서로 답이 안 되거나 특정 함수·설정 키·
에러 문구의 실제 위치를 확인해야 할 때만 search_code 로 찾고 read_code 로 그 부근을 읽는다.
리포 이름은 search_docs 결과 경로의 앞부분(<그룹>/<리포>)이다. 코드는 하루 한 번 맞추므로 그날 올라온 변경은 없을 수 있다.
"""

server = MCPServer(name="git-docs", instructions=INSTRUCTIONS + (CODE_INSTRUCTIONS if MODE == "clone" else ""))


# docstring 이 도구 설명이 된다. 모델이 이 도구를 부를지 정할 때 읽는 문장이다.
@server.tool()
def search_docs(query: str) -> str:
    """팀 내부 문서에서 질문과 관련된 부분을 찾는다.

    사내 GitLab 리포의 README·운영 문서·배포 절차·장애 대응 기록·설계 문서가 대상이다.
    사내 프로젝트나 서비스 이름, 우리 팀의 작업 방식, 사내 설정값을 묻는 질문에 쓴다.
    일반 프로그래밍 지식이나 공개 라이브러리 사용법에는 쓰지 않는다.

    query 에는 질문을 자연어 그대로 넣는다. 서비스 이름·에러 코드·설정 키 같은
    식별자는 그대로 넣으면 정확히 일치하는 문서를 찾는다.
    결과는 관련도 순 조각 5개이고, 각 조각 첫 줄에 [문서 경로 > 헤딩 | 수정 날짜] 가 붙는다.
    """
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


if MODE == "clone":
    from cloner import code

    server.add_tool(code.search_code)
    server.add_tool(code.read_code)


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
