"""
The headers this app cannot get wrong.

escalasPT sends `camera=(), geolocation=()`, which denies both APIs to its own
origin, and a CSP without blob:. Copied verbatim into a camera-and-GPS app, the
shutter button does nothing and local photo thumbnails never render — with no
network error to point at. This test is the cheap guard against that regression.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_camera_and_geolocation_granted_to_self(client):
    response = await client.get("/api/health")
    policy = response.headers["Permissions-Policy"]

    assert "camera=(self)" in policy
    assert "geolocation=(self)" in policy
    assert "camera=()" not in policy
    assert "geolocation=()" not in policy


@pytest.mark.asyncio
async def test_csp_allows_service_worker_and_local_blobs(client):
    csp = (await client.get("/api/health")).headers["Content-Security-Policy"]

    assert "worker-src 'self' blob:" in csp     # service worker + MapLibre workers
    assert "blob:" in csp.split("img-src")[1].split(";")[0]  # local photo previews
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
async def test_csp_allows_no_external_origins(client):
    """The app never talks to the internet — not even for fonts."""
    csp = (await client.get("/api/health")).headers["Content-Security-Policy"]

    assert "fonts.googleapis" not in csp
    assert "gstatic" not in csp
    assert "font-src 'self'" in csp


@pytest.mark.asyncio
async def test_standard_hardening_headers(client):
    headers = (await client.get("/api/health")).headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "max-age=" in headers["Strict-Transport-Security"]
