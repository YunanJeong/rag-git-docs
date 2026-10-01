"""무엇을 새로 받고 무엇을 지울지 정한다. 경로와 blob SHA 만 보고 판단한다."""

from __future__ import annotations

Files = dict[str, str]  # 파일 경로 → blob SHA


def changed(known: Files, live: Files) -> list[str]:
    """새로 받을 파일. SHA 는 내용의 해시라 내용이 같으면 다시 받지 않는다."""
    return sorted(p for p, sha in live.items() if known.get(p) != sha)


def deleted(known: Files, live: Files) -> list[str]:
    """지울 파일. 기록에 있는 것만 대상이라 수집기가 쓰지 않은 파일은 건드리지 않는다."""
    return sorted(p for p in known if p not in live)


def vanished(manifest: dict[str, Files], active: set[str]) -> list[str]:
    """지울 리포. 조회에 실패한 리포도 active 에 넣어야 일시 장애로 문서가 지워지지 않는다."""
    return sorted(r for r in manifest if r not in active)
