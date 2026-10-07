"""Offline tests: a fake HTTP layer stands in for the API, so no key or network is needed."""
import io
import json
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import seedance25  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def fake_api(monkeypatch, statuses, calls):
    def urlopen(request, timeout=None):
        calls.append((request.get_method(), request.full_url, request.data))
        url = request.full_url
        if url.endswith("/videos/generations"):
            return FakeResponse(json.dumps({"request_id": "req_1", "status": "pending"}).encode())
        if url.endswith("/content"):
            return FakeResponse(b"MP4")
        if "/videos/req_1" in url:
            return FakeResponse(json.dumps(statuses.pop(0)).encode())
        raise AssertionError(url)

    monkeypatch.setattr(seedance25.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(seedance25.time, "sleep", lambda s: None)


def test_generate_submits_polls_and_downloads(monkeypatch, tmp_path):
    calls = []
    fake_api(monkeypatch, [
        {"status": "pending", "progress": 40},
        {"status": "done", "progress": 100, "usage": {"output_seconds": 5, "reference_video_seconds": 0, "billed_seconds": 5}},
    ], calls)
    client = seedance25.Seedance25(api_key="test")
    job = client.generate("a fox in snow", str(tmp_path / "out.mp4"), duration=5, resolution="720p")

    method, url, body = calls[0]
    assert (method, url) == ("POST", "https://argolink.io/v1/videos/generations")
    assert json.loads(body) == {"model": "seedance-2.5", "prompt": "a fox in snow", "duration": 5, "resolution": "720p"}
    assert calls[-1][1] == "https://argolink.io/v1/videos/req_1/content"
    assert (tmp_path / "out.mp4").read_bytes() == b"MP4"
    assert job["usage"]["billed_seconds"] == 5


@pytest.mark.parametrize("state", ["failed", "expired"])
def test_terminal_states_raise(monkeypatch, state):
    fake_api(monkeypatch, [{"status": state, "error": {"code": "invalid_input"}}], [])
    with pytest.raises(seedance25.SeedanceError) as raised:
        seedance25.Seedance25(api_key="test").wait("req_1")
    assert raised.value.body["status"] == state


def test_http_errors_keep_status_and_body(monkeypatch):
    def urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error":"seed is not supported"}'))

    monkeypatch.setattr(seedance25.urllib.request, "urlopen", urlopen)
    with pytest.raises(seedance25.SeedanceError) as raised:
        seedance25.Seedance25(api_key="test").submit("x", seed=1)
    assert raised.value.status == 400
    assert raised.value.body == {"error": "seed is not supported"}


def test_base_url_can_be_overridden(monkeypatch):
    monkeypatch.setenv("SEEDANCE_BASE_URL", "https://example.test/v1/")
    assert seedance25.Seedance25(api_key="test").base_url == "https://example.test/v1"


def test_missing_key_is_reported(monkeypatch):
    monkeypatch.delenv("SEEDANCE_API_KEY", raising=False)
    with pytest.raises(seedance25.SeedanceError):
        seedance25.Seedance25()


def test_every_request_sends_a_user_agent(monkeypatch, tmp_path):
    agents = []
    fake_api(monkeypatch, [{"status": "done", "usage": {}}], [])
    fake = seedance25.urllib.request.urlopen

    def urlopen(request, timeout=None):
        agents.append(request.get_header("User-agent"))
        return fake(request, timeout)

    monkeypatch.setattr(seedance25.urllib.request, "urlopen", urlopen)
    seedance25.Seedance25(api_key="test").generate("x", str(tmp_path / "out.mp4"))
    assert agents and all(agent == seedance25.USER_AGENT for agent in agents)
