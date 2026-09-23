"""무엇을 받고 무엇을 지울지 정한다.

git pull 이 공짜로 해주던 판단을 직접 하는 부분이다. 경로 → blob SHA 만 다루므로
어느 소스에서 왔는지 모르고, 가져다 쓰는 모듈이 하나도 없다. 문서가 날아가는 자리라
네트워크도 디스크도 닿지 않게 두고 테스트로 묶는다.
"""

from __future__ import annotations

Files = dict[str, str]  # 경로 → blob SHA


def changed(known: Files, live: Files) -> list[str]:
    """이번에 새로 받아야 할 경로.

    SHA 는 내용의 해시다. 그래서 브랜치 이름이 바뀌어도, 파일을 옮겼다 되돌려도,
    내용이 같으면 다시 받지 않는다. 수정 시각 기반이었다면 전부 재다운로드다.
    """
    return sorted(p for p, sha in live.items() if known.get(p) != sha)


def deleted(known: Files, live: Files) -> list[str]:
    """manifest 에 있는데 이번 목록에 없는 경로.

    manifest 를 기준으로 계산하므로 수집기가 기록한 적 없는 파일은 삭제 대상이 될 수
    없다. DOCS_DIR 을 잘못 잡았을 때 남의 파일을 안 건드리는 보장이 여기서 나온다.
    """
    return sorted(p for p in known if p not in live)


def vanished(manifest: dict[str, Files], active: set[str]) -> list[str]:
    """manifest 에 있는데 이번 대상에 없는 리포.

    리포가 지워진 경우와 제외 목록에 추가된 경우가 같은 판정이다.
    조회에 실패한 리포는 호출자가 active 에 넣어 여기 걸리지 않게 해야 한다 —
    일시 장애를 "리포가 사라졌다" 로 읽으면 그 리포 문서가 통째로 날아간다.
    """
    return sorted(r for r in manifest if r not in active)
