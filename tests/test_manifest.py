
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.manifest import changed, deleted, vanished  # noqa: E402


def test_changed_skips_same_sha():
    known = {"a.md": "111", "b.md": "222"}
    live = {"a.md": "111", "b.md": "222"}
    assert changed(known, live) == [], "SHA 가 같은데 다시 받으려 한다"


def test_changed_includes_new_and_modified():
    known = {"a.md": "111", "b.md": "222"}
    live = {"a.md": "999", "b.md": "222", "c.md": "333"}
    assert changed(known, live) == ["a.md", "c.md"], "바뀐 파일과 새 파일이 안 잡혔다"


def test_changed_on_empty_manifest_takes_everything():
    """첫 실행. manifest 가 없으면 전량 수집이다."""
    live = {"a.md": "1", "b.md": "2"}
    assert changed({}, live) == ["a.md", "b.md"], "첫 실행에서 전량을 안 받는다"


def test_deleted_finds_missing_path():
    known = {"a.md": "1", "old.md": "2"}
    live = {"a.md": "1"}
    assert deleted(known, live) == ["old.md"], "지워진 파일을 못 찾았다"


def test_deleted_is_manifest_only():
    """수집기가 기록한 적 없는 파일은 삭제 후보가 될 수 없다.

    DOCS_DIR 을 잘못 잡았을 때 남의 파일을 안 지운다는 보장이 이 성질이다.
    """
    known = {"a.md": "1"}
    live = {"a.md": "1", "남이-둔-파일.md": "2"}
    assert deleted(known, live) == [], "manifest 에 없는 파일이 삭제 목록에 들었다"


def test_vanished_detects_removed_repo():
    manifest = {"org/docs": {"a.md": "1"}, "org/legacy": {"b.md": "2"}}
    assert vanished(manifest, {"org/docs"}) == ["org/legacy"], "사라진 리포를 못 찾았다"


def test_vanished_treats_excluded_repo_the_same():
    """리포가 지워진 경우와 제외 목록에 추가된 경우는 같은 판정이다."""
    manifest = {"org/docs": {"a.md": "1"}, "org/skip": {"b.md": "2"}}
    assert vanished(manifest, {"org/docs"}) == ["org/skip"], "제외된 리포가 안 잡혔다"


def test_vanished_spares_failed_repo():
    """조회에 실패해도 호출자가 active 에 넣으면 삭제 대상이 아니다.

    일시 장애를 "리포가 사라졌다" 로 읽으면 그 리포 문서가 통째로 날아간다.
    """
    manifest = {"org/docs": {"a.md": "1"}, "org/broken": {"b.md": "2"}}
    active = {"org/docs", "org/broken"}  # broken 은 500 이 났지만 대상이었다
    assert vanished(manifest, active) == [], "실패한 리포가 삭제 대상이 됐다"


def test_vanished_on_empty_manifest_deletes_nothing():
    assert vanished({}, set()) == [], "빈 manifest 에서 삭제가 나왔다"
