import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cloner import state  # noqa: E402
from collector.files import load_manifest  # noqa: E402


def test_roundtrip(tmp_path):
    state.save(tmp_path, {"g/r": "abc"}, {"g/r/README.md": "2026-01-02"})
    assert state.load(tmp_path) == ({"g/r": "abc"}, {"g/r/README.md": "2026-01-02"})


def test_first_run_is_empty(tmp_path):
    assert state.load(tmp_path) == ({}, {})


def test_clone_refuses_api_manifest(tmp_path):
    """api 방식이 쓰던 디렉터리에 clone 하면 md 사본과 clone 이 한 경로에서 부딪힌다."""
    (tmp_path / ".manifest.json").write_text(json.dumps({"files": {}, "dates": {}}))
    with pytest.raises(ValueError):
        state.load(tmp_path)


def test_api_refuses_clone_manifest(tmp_path):
    """clone 기록을 api 의 옛 형식으로 읽으면 clone 디렉터리에 md 를 덮어쓴다."""
    state.save(tmp_path, {"g/r": "abc"}, {})
    with pytest.raises(ValueError):
        load_manifest(tmp_path)


def test_dates_key_is_shared_with_index(tmp_path):
    """index.py 의 load_dates 는 방식을 모른 채 dates 만 읽는다."""
    state.save(tmp_path, {"g/r": "abc"}, {"g/r/a.md": "2026-01-02"})
    assert json.loads((tmp_path / ".manifest.json").read_text())["dates"] == {"g/r/a.md": "2026-01-02"}


def test_vanished_spares_failed_repo():
    heads = {"g/ok": "1", "g/broken": "2", "g/gone": "3"}
    assert state.vanished(heads, {"g/ok", "g/broken"}) == ["g/gone"]


def test_vanished_is_manifest_only():
    assert state.vanished({}, {"g/new"}) == []
