"""진입점 3 — 검색을 MCP 서버로 띄운다. Claude Code 가 붙어 search_docs 를 부른다.

질문도 문서 조각과 같은 모델(bge-m3)로 벡터로 바꿔야 비교가 된다. 그래서 색인에 쓴
indexer.embed 를 여기서도 쓴다. 모델은 기동 때 한 번만 올려 검색 한 번이 수십 ms 안에 끝난다.

네트워크에 열리므로 모든 요청에 사용자별 토큰(Authorization: Bearer <토큰>)을 요구하고, 도구 호출마다 누가 불렀는지 로그에 남긴다.
토큰은 SERVE_TOKEN 에 '이름:토큰' 을 쉼표로 이어 넣는다.
AUTH_MODE=none 은 자기 PC 에서만 쓰는 로컬 실행용이라 인증이 없고, SERVE_HOST 가 127.0.0.1 일 때만 뜬다.

COLLECT_MODE=clone 이면 DOCS_DIR 의 clone 을 읽는 코드 도구(search_code, read_code, code_history)를 함께 노출한다.
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from qdrant_client import models

import auth
from indexer import store
from indexer.embed import Embedder

MODE = os.environ.get("COLLECT_MODE", "api")
if MODE not in ("api", "clone"):
    sys.exit(f"COLLECT_MODE 는 api 또는 clone 이다: {MODE}")
if MODE == "clone" and not os.environ.get("DOCS_DIR"):
    sys.exit("COLLECT_MODE=clone 이면 clone 이 있는 DOCS_DIR 이 필요하다")
AUTH_MODE = os.environ.get("AUTH_MODE", "token")
if AUTH_MODE not in ("token", "none"):
    sys.exit(f"AUTH_MODE 는 token 또는 none 이다: {AUTH_MODE}")
# 인증이 없으므로 이 PC 밖에서 붙을 수 없을 때만 띄운다
if AUTH_MODE == "none" and os.environ.get("SERVE_HOST", "0.0.0.0") not in ("127.0.0.1", "localhost", "::1"):
    sys.exit("AUTH_MODE=none 은 인증이 없어 SERVE_HOST=127.0.0.1 일 때만 뜬다")

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
# 코드 도구는 느리고 토큰을 많이 쓴다. 문서 검색으로 끝날 질문에서 코드를 뒤지지 않도록 기준을 못박는다.
CODE_INSTRUCTIONS = """
같은 리포들의 코드와 커밋 이력을 읽는 도구(search_code, read_code, code_history)도 있다. 이 도구들은 예외적으로만 쓴다.
- 항상 search_docs 를 먼저 부르고, 문서로 답이 되면 코드 도구를 부르지 않는다. 확인 삼아, 덧붙이려고 코드를 보지 않는다.
- 코드 도구는 둘 중 하나일 때만 쓴다: 사용자가 코드·구현·변경 이력을 직접 물었을 때, 또는 문서에 답이 없어 특정 함수·설정 키·에러 문구의 위치나 바뀐 시점을 확인해야만 답할 수 있을 때.
- 쓸 때는 리포와 경로를 좁혀 몇 번 안에 끝낸다. 리포 전체를 훑거나 관련 파일을 차례로 다 읽지 않는다. 찾지 못하면 거기서 멈추고 찾지 못했다고 말한다.
리포 이름은 search_docs 결과 경로의 앞부분(<그룹>/<리포>)이다. 코드는 주기적으로 맞추므로 최근 변경은 없을 수 있다.
"""

server = MCPServer(name="git-docs", instructions=INSTRUCTIONS + (CODE_INSTRUCTIONS if MODE == "clone" else ""))


# docstring 이 도구 설명이 된다. 모델이 이 도구를 부를지 정할 때 읽는 문장이다.
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


TOOLS = [search_docs]
if MODE == "clone":
    from cloner import code

    TOOLS += [code.search_code, code.read_code, code.code_history]


if __name__ == "__main__":
    users: dict[str, str] = {}
    if AUTH_MODE == "token":
        raw = os.environ.get("SERVE_TOKEN")
        if not raw:
            # 검색 서버 토큰 없이 네트워크에 열리는 일이 없도록 아예 뜨지 않는다
            sys.exit("SERVE_TOKEN 이 필요하다")
        try:
            users = auth.parse_tokens(raw)
        except ValueError as e:
            sys.exit(str(e))
    for tool in TOOLS:
        server.add_tool(auth.audited(tool, users, anonymous="local" if AUTH_MODE == "none" else "-"))

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    auth.log.addHandler(handler)
    auth.log.setLevel(logging.INFO)
    auth.log.propagate = False
    # SDK 는 127.0.0.1 로 들어온 요청만 통과시키는 Host 헤더 검사를 켜 둔다.
    # Service 를 거쳐 노드 IP 로 들어오는 요청이 막히지 않게 끄고, 검색 서버 토큰으로 막는다.
    app = server.streamable_http_app(
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    uvicorn.run(
        auth.require_token(app, users) if AUTH_MODE == "token" else app,
        host=os.environ.get("SERVE_HOST", "0.0.0.0"),
        port=8765,
        log_level="warning",
    )
