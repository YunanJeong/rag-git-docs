"""clone 방식의 수집 기록(.manifest.json). 리포마다 마지막으로 맞춘 커밋과, 문서별 마지막 커밋일을 둔다.

파일 이름과 dates 형식은 api 방식과 같다. index.py 가 방식을 모른 채 dates 를 읽는다.
mode 로 api 방식의 기록과 구별해, 두 방식이 한 디렉터리를 같이 쓰는 사고를 막는다.
"""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST = ".manifest.json"
MODE = "clone"


def load(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(리포 경로 → 커밋 해시, "리포/파일" → 마지막 커밋일). 처음 실행이면 둘 다 비어 있다."""
    path = root / MANIFEST
    if not path.exists():
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("mode") != MODE:
        raise ValueError(f"api 방식의 수집 기록이 있는 디렉터리다: {root}")
    return data["heads"], data["dates"]


def save(root: Path, heads: dict[str, str], dates: dict[str, str]) -> None:
    data = {"mode": MODE, "heads": heads, "dates": dates}
    (root / MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def vanished(heads: dict[str, str], active: set[str]) -> list[str]:
    """지울 clone. 기록에 있는 것만 대상이라, 수집기가 만들지 않은 디렉터리는 건드리지 않는다.

    조회에 실패한 리포도 active 에 넣어야 일시 장애로 clone 이 지워지지 않는다.
    """
    return sorted(r for r in heads if r not in active)
