"""Seedance 2.5 API client: submit a video job, wait for it, download the MP4.

Standard library only (Python 3.9+). Works against any endpoint that speaks the
/v1/videos protocol; the default base URL is ArgoLink's.

    export SEEDANCE_API_KEY=...
    python seedance25.py "A slow aerial shot over a foggy pine forest at sunrise"
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://argolink.io/v1"
MODEL = "seedance-2.5"
TERMINAL = ("done", "failed", "expired")


class SeedanceError(RuntimeError):
    """A request was rejected or a job ended without a video."""

    def __init__(self, message: str, status: int | None = None, body: object = None):
        super().__init__(message)
        self.status = status
        self.body = body


class Seedance25:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: float = 60):
        self.api_key = api_key or os.environ.get("SEEDANCE_API_KEY")
        if not self.api_key:
            raise SeedanceError("set SEEDANCE_API_KEY or pass api_key")
        self.base_url = (base_url or os.environ.get("SEEDANCE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None, raw: bool = False):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.api_key}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as error:
            text = error.read().decode(errors="replace")
            try:
                detail = json.loads(text)
            except ValueError:
                detail = text
            raise SeedanceError(f"{method} {path} returned {error.code}: {text[:300]}", error.code, detail) from None
        return payload if raw else json.loads(payload)

    def submit(self, prompt: str, **fields) -> str:
        """Start a job and return its request_id. fields: duration, resolution,
        aspect_ratio, start_image, end_image, reference_images, reference_videos,
        reference_audios, omni_reference_task_type, generate_audio."""
        job = self._request("POST", "/videos/generations", {"model": MODEL, "prompt": prompt, **fields})
        return job["request_id"]

    def status(self, request_id: str) -> dict:
        return self._request("GET", f"/videos/{request_id}")

    def wait(self, request_id: str, interval: float = 5, max_wait: float = 1800, on_progress=None) -> dict:
        """Poll until the job is done; raise if it fails, expires or runs past max_wait."""
        deadline = time.monotonic() + max_wait
        while True:
            job = self.status(request_id)
            state = job.get("status")
            if state == "done":
                return job
            if state in TERMINAL:
                raise SeedanceError(f"job {request_id} ended as {state}", body=job)
            if on_progress:
                on_progress(job)
            if time.monotonic() > deadline:
                raise SeedanceError(f"job {request_id} still {state} after {max_wait:.0f}s", body=job)
            time.sleep(interval)

    def download(self, request_id: str, path: str = "output.mp4") -> str:
        with open(path, "wb") as handle:
            handle.write(self._request("GET", f"/videos/{request_id}/content", raw=True))
        return path

    def upload(self, file_path: str, kind: str, content_type: str) -> str:
        """Upload a local image, video or audio file and return the media_url to
        put in start_image, end_image or a reference list. kind: image, video or audio."""
        size = os.path.getsize(file_path)
        ticket = self._request("POST", "/media/uploads", {
            "model": MODEL, "type": kind, "content_type": content_type, "size_bytes": size,
        })
        with open(file_path, "rb") as handle:
            put = urllib.request.Request(ticket["upload_url"], data=handle.read(), method="PUT")
        put.add_header("Content-Type", content_type)
        urllib.request.urlopen(put, timeout=self.timeout).close()
        return ticket["media_url"]

    def generate(self, prompt: str, path: str = "output.mp4", **fields) -> dict:
        """submit + wait + download. Returns the final job, whose usage holds the billed seconds."""
        request_id = self.submit(prompt, **fields)
        job = self.wait(request_id, on_progress=lambda j: print(f"{j.get('progress', 0)}%", file=sys.stderr))
        self.download(request_id, path)
        return job


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('usage: python seedance25.py "your prompt" [output.mp4]')
    result = Seedance25().generate(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "output.mp4",
                                   duration=5, resolution="720p", aspect_ratio="16:9")
    print(json.dumps(result.get("usage", {})))
