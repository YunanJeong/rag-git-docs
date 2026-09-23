# 작업 지시: 마크다운 RAG 최소 구현

격리된 새 세션에서 그대로 수행 가능한 자족적 지시서다. 선행 대화 없음을 전제한다.

## 0. 이 작업의 목적

**RAG 파이프라인이 실제로 어떻게 도는지 코드로 확인하는 것.** 제품을 만드는 게 아니다.
전체가 300줄 안쪽이어야 하고, 사람이 한 번에 읽어서 이해할 수 있어야 한다.

```
로컬 md 파일  →  청킹  →  임베딩  →  Qdrant 저장  →  질의 임베딩  →  유사도 검색  →  관련 조각
```

각 화살표가 파일 하나에 대응한다. 이 대응 관계가 코드에서 눈에 보이는 것이 이 작업의 성과물이다.

---

## 1. 만들지 않는 것

요청받지 않았다면 넣지 말 것. 하나씩 다 이유가 있다.

| 안 만드는 것 | 이유 |
|---|---|
| LLM 답변 생성 | 검색 조각 반환까지가 이번 범위. 생성 모델 호출 코드 일절 없음 |
| 증분 색인 / 변경 감지 | **매번 전량 재색인한다.** md 1천 개면 몇 분이다. 증분은 이해에 기여하지 않고 코드만 두 배로 만든다 |
| 추상 인터페이스 (Protocol, 팩토리, 플러그인) | 구현체가 하나뿐인데 인터페이스를 두면 읽는 사람이 한 겹 더 뚫어야 한다 |
| 설정 dataclass 계층 | 환경변수 5개면 충분하다 |
| 웹 서버 / UI / FastAPI | CLI 두 개로 끝 |
| 인프라 코드 (Terraform, Compose, systemd) | Qdrant 실행 명령 한 줄을 README 에 적는 것까지만 |
| 리랭커, 배치 스케줄러, dry-run 플래그 | |

나중에 GitLab 연동이나 증분 색인이 붙을 수는 있다. **하지만 지금 그걸 대비한 구조를 만들지
않는다.** 코드가 짧으면 그때 고쳐 쓰는 게 지금 추상화하는 것보다 싸다.

---

## 2. 재사용 요건 (이것만 지키면 됨)

로컬에서 짜고, 나중에 원격 인스턴스에 그대로 올려 돌릴 수 있어야 한다. 필요한 건 두 가지뿐이다.

1. **경로와 접속 정보를 코드에 박지 않는다.** `DOCS_DIR`, `QDRANT_URL` 을 환경변수로 읽는다.
   원격에서 바뀌는 건 이 둘뿐이다.
2. **`uv` 로 의존성을 고정한다.** `pyproject.toml` + `uv.lock` 을 커밋해 다른 머신에서
   `uv sync` 한 번에 같은 버전이 서게 한다. `requirements.txt` 를 쓰지 않는다.

그 이상의 이식성 장치(설정 파일 포맷, 프로파일, Docker 이미지 빌드)는 넣지 않는다.

---

## 3. 스택 (확정, 재검토 금지)

| 레이어 | 선택 | 이유 |
|---|---|---|
| Vector DB | **Qdrant** (Docker 컨테이너 1개) | 로컬 실행이 한 줄. sparse 벡터를 기본 지원 |
| 임베딩 | **bge-m3** (`BAAI/bge-m3`), 로컬 실행 | 한국어 성능이 좋고, dense 와 sparse 를 한 번의 추론으로 함께 낸다. 문서가 외부로 안 나가고 API 키가 필요 없다 |
| 임베딩 라이브러리 | `FlagEmbedding` | Ollama·OpenAI 호환 엔드포인트는 dense 만 주고 sparse 를 버린다 |
| 언어 | Python 3.11+ | |

모델 파일 약 2.3GB 를 최초 실행 시 내려받는다.

### dense 와 sparse 를 둘 다 쓰는 이유 (핵심 개념)

- **dense** — 1024개 실수로 된 "의미 좌표". 표현이 달라도 뜻이 같으면 가까이 놓인다.
  질의 `쿠버네티스 워커 늘리기` 로 문서 `노드그룹 desired 조정` 을 찾아낸다.
  대신 학습 데이터에 없는 사내 고유명사를 구별 못 한다 — `kr-mum`, `kr-sum` 이 뭉친다.
- **sparse** — 단어 하나가 축 하나인 희소 벡터. 값은 학습된 중요도 가중치.
  `serverid`, `kr-mum`, 에러코드, 명령어처럼 **정확히 일치해야 하는 토큰**을 잡는다.

둘을 각각 검색한 뒤 순위를 합친다. 어느 한쪽만으로는 사내 기술 문서 검색이 성립하지 않는다.
**이 두 방식의 차이를 직접 눈으로 확인하는 것이 7절 검증의 목적이다.**

---

## 4. 레포 구조

루트는 `~/private/docs-rag-vector-db` (빈 git 레포가 이미 있다).

```
docs-rag-vector-db/
├── rag/
│   ├── __init__.py
│   ├── chunk.py        md 텍스트 → 조각 리스트
│   ├── embed.py        텍스트 리스트 → dense + sparse 벡터
│   └── store.py        Qdrant 컬렉션 생성 / 저장 / 검색
├── index.py            진입점 1 — 디렉터리를 통째로 색인
├── search.py           진입점 2 — 질의하고 결과 출력
├── tests/
│   ├── test_chunk.py   모델·DB 없이 도는 단위 테스트
│   └── sample-docs/*.md
├── pyproject.toml      의존성 정의 (uv)
├── uv.lock             잠금 파일. 커밋한다
├── .env.example        자리표시자만. 실제 값 금지
└── README.md
```

패키지 관리는 **uv** 로 한다. `uv sync` 로 환경을 만들고 `uv run index.py` 로 실행한다.
`pip`·`requirements.txt`·수동 venv 를 쓰지 않는다.

`rag/` 안의 세 파일은 서로를 import 하지 않는다. `index.py` 와 `search.py` 만 그것들을 쓴다.
이 방향이 지켜지면 나중에 API 서버를 얹을 때 `rag/` 를 건드릴 일이 없다.

---

## 5. `rag/chunk.py`

마크다운 문서 하나를 검색 단위 조각으로 자른다. 임베딩 모델도 Qdrant 도 import 하지 않는다.

```
chunk_markdown(text: str, doc_path: str, max_chars: int = 1200) -> list[Chunk]
```

`Chunk` 는 dataclass: `doc_path`, `chunk_index`, `heading_path: list[str]`, `text`.

규칙 — 순서대로 지킨다.

1. **코드펜스(` ``` `, `~~~`)를 먼저 인식한다.** 펜스 안의 `#` 은 헤더가 아니다.
   셸 주석 든 md 가 엉뚱하게 쪼개지는 걸 막는다. 펜스는 중간에서 자르지 않는다.
2. `#` ~ `######` 로 섹션을 나누고 각 섹션에 `heading_path` 를 매긴다.
3. 섹션이 `max_chars` 를 넘으면 **빈 줄(단락) 경계**로 더 쪼갠다.
4. 각 조각 맨 앞에 브레드크럼 한 줄을 붙인다: `[ops/scaling.md > 운영 > 스케일링]`.
   조각만 떼면 맥락이 없어 임베딩 품질이 떨어진다. **생략하지 말 것.**
5. 공백뿐인 조각은 버린다.

토큰이 아니라 **글자 수**로 자른다. 토크나이저를 끌어오면 이 파일이 모델에 의존하게 되고
테스트가 모델 다운로드를 요구하게 된다. 정확도보다 독립성이 중요하다.

---

## 6. `rag/embed.py`

```
class Embedder:
    def __init__(self, model_name="BAAI/bge-m3")
    def encode(self, texts: list[str]) -> tuple[list[list[float]], list[dict[int, float]]]
```

`(dense 벡터들, sparse 벡터들)` 을 반환. sparse 는 `{토큰인덱스: 가중치}`.

- `FlagEmbedding.BGEM3FlagModel(...).encode(texts, return_dense=True, return_sparse=True,
  return_colbert_vecs=False)`. colbert 는 안 쓴다.
- **모델은 첫 `encode` 호출 때 로딩한다.** import 만으로 2.3GB 를 올리지 않게.
- 반환된 `lexical_weights` 의 키가 문자열로 오므로 **`int` 로 변환한다.**
  Qdrant sparse 인덱스는 정수여야 한다. 안 하면 저장 시점에 터진다.
- 질의와 문서에 같은 함수를 쓴다 (bge-m3 는 질의 접두사가 필요 없다).

---

## 7. `rag/store.py`

Qdrant 클라이언트를 감싼다.

```
recreate_collection(dim: int = 1024)      # 있으면 지우고 새로 만든다
upsert(chunks, dense_vecs, sparse_vecs)   # 64~128개씩 나눠 전송
search(dense_vec, sparse_vec, top_k=5) -> list[하이트]
count() -> int
```

컬렉션 스키마:
- named dense 벡터 `"dense"`, 크기 1024, 거리 **Cosine**
- named sparse 벡터 `"sparse"`
- payload: `doc_path`, `chunk_index`, `heading_path`, `text`
- point id: `chunk_index` 를 포함한 연속 정수 또는 `sha1(f"{doc_path}#{chunk_index}")`

`recreate_collection` 이 매번 지우고 새로 만들기 때문에 **삭제된 문서의 조각이 남는 문제가
아예 생기지 않는다.** 증분 색인을 안 하는 대신 얻는 단순함이다.

### 검색

`qdrant-client` 의 Query API `prefetch` + RRF 융합을 쓴다. dense 와 sparse 를 각각 20개
뽑아 순위를 합쳐 상위 `top_k` 를 낸다.

> **주의**: Query API 와 sparse 관련 클래스명·시그니처는 `qdrant-client` 버전마다 다르다.
> **기억으로 쓰지 말고 설치된 버전의 실제 시그니처를 확인한 뒤 작성한다.**
> RRF 를 지원하지 않는 버전이면 두 검색을 따로 호출하고 직접 계산한다:
> `score = Σ 1/(60 + rank)`.

---

## 8. 진입점

### `index.py`

```
python index.py
```

1. `DOCS_DIR` 아래를 재귀 순회해 `.md` 파일을 모은다 (`.git/`, `node_modules/`, `.venv/` 제외)
2. `recreate_collection()`
3. 파일마다 읽어서 `chunk_markdown`
4. 전체 조각을 **배치로 묶어** `encode` — 한 건씩 부르면 수십 배 느리다
5. `upsert`
6. 처리한 파일 수·조각 수를 출력

진행 상황을 파일 단위로 stderr 에 찍는다. 몇 분 걸리는데 아무것도 안 나오면 멈춘 것과
구별이 안 된다.

### `search.py`

```
python search.py "쿠버네티스 워커 어떻게 늘려?"
python search.py "kr-mum" --top-k 3
```

질의를 `encode` 하고 `search` 를 부른 뒤, 결과마다 **점수 / 문서경로 / 헤딩경로 / 본문 앞부분**을
사람이 읽을 수 있게 출력한다.

---

## 9. 설정 (환경변수)

`.env.example` 에 자리표시자만 적는다. 실제 값을 저장소에 넣지 않는다.

| 변수 | 기본값 | 용도 |
|---|---|---|
| `DOCS_DIR` | (필수) | 색인할 md 디렉터리 |
| `QDRANT_URL` | `http://localhost:6333` | |
| `QDRANT_COLLECTION` | `docs` | |
| `EMBED_MODEL` | `BAAI/bge-m3` | |
| `TOP_K` | `5` | |

`os.environ.get` 으로 직접 읽는다. 설정 클래스를 만들지 않는다.

---

## 10. 구현 순서와 검증

한 단계 검증이 끝난 뒤 다음으로 간다.

| 단계 | 만드는 것 | 확인 |
|---|---|---|
| 1 | `rag/chunk.py` + `tests/test_chunk.py` | **모델·DB 없이** 테스트 통과. 코드펜스 안의 `#`, 중첩 헤더, 긴 섹션 분할, 브레드크럼 부착을 케이스로 포함 |
| 2 | `rag/embed.py` | 짧은 문장 2건 인코딩 → dense 길이 1024, sparse 가 비어있지 않음 |
| 3 | `rag/store.py` | 컬렉션 생성 → 더미 조각 3개 저장 → `count()` 가 3 → 검색이 결과를 냄 |
| 4 | `index.py` | 실제 md 디렉터리 색인. 두 번 돌려도 조각 수가 같은지 (재생성이므로 같아야 함) |
| 5 | `search.py` | 아래 두 질의를 각각 확인 |

### 완료 기준 — 이게 눈으로 보이면 끝이다

1. **의미 질의**: 문서에 없는 표현으로 물어도 맞는 문서가 나온다.
   예) 문서에 `노드그룹 desired 조정` 만 있는데 `워커 늘리는 법` 으로 찾힌다 → **dense 가 일한 것**
2. **고유명사 질의**: `kr-mum` 같은 사내 식별자가 정확히 그 문서를 찾는다 → **sparse 가 일한 것**
3. `README.md` 에 Qdrant 실행 명령 한 줄, 환경변수 표, 두 CLI 사용 예시

---

## 11. 코딩 방침

- 타입 힌트를 붙인다. `from __future__ import annotations`.
- **영리한 장치를 얹지 않는다.** dry-run 플래그, 진행률 바, 재시도 래퍼, 캐시 계층 없음.
- 주석은 "왜"를 적는다. 개념이 처음인 사람이 읽는다는 전제로, dense/sparse 처럼
  **비직관적인 부분에만** 짧게 단다. 자명한 줄에 주석 달지 않는다.
- 실패를 조용히 삼키지 않는다. 파일 디코드 실패는 경고 찍고 건너뛰되 마지막에 집계해 보고.
- 시크릿·토큰·실제 계정 ID 를 코드·로그·예시에 넣지 않는다.
- **`git commit` 을 실행하지 않는다.** 파일 변경까지만 하고 저장소 반영은 사용자가 한다.

---

## 12. 실행 환경 (확인 완료 — 물을 것 없음)

- **`DOCS_DIR` = `tests/sample-docs`.** 색인 대상 md 를 직접 만들어야 한다. 아래 조건을 만족하는
  샘플 4개 내외를 작성한다. 이게 곧 10절 완료 기준의 검증 데이터다.
  - 문서 하나에는 `워커`·`늘리다` 라는 말을 **쓰지 않고** `노드그룹 desired 조정` 같은
    표현만 담는다 → dense 검증용
  - 문서 하나에는 `kr-mum` 같은 사내 고유 식별자를 담고, **다른 문서에는 `kr-sum` 처럼
    비슷하지만 다른 식별자**를 담는다 → sparse 검증용. 둘이 구별되어야 통과다
  - 코드펜스 안에 `# 주석` 이 든 문서를 하나 포함한다 → 청킹 검증용
  - 긴 섹션(단락 여러 개)이 든 문서를 하나 포함한다 → 분할 검증용
- **Docker 사용 가능.** Qdrant 는 컨테이너로 띄운다. `:memory:` 대체 경로는 쓰지 않는다.
- **bge-m3 내려받기 가능.** `HashingEmbedder` 같은 대체 백엔드를 만들지 않는다.
  실제 모델로 검증한다.
