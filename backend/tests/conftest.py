import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.api import create_app          # noqa: E402
from app.config import PRESETS, Settings   # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Keys and REFORM3D_* variables on the machine running the tests must never change what a test sees."""
    names = {v[1] for v in PRESETS.values() if v[1]} | {"ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "CLOUDFLARE_ACCOUNT_ID"}
    names |= {k for k in os.environ if k.startswith("REFORM3D_")}
    for n in names:
        monkeypatch.delenv(n, raising=False)


def make_settings(tmp_path, **over) -> Settings:
    """Explicit values for everything a test depends on, so the environment of the machine never leaks in."""
    base = dict(data_dir=tmp_path / "data", api_key="", enable_llm=False, enable_design=True, llm_provider="anthropic", llm_api_key="", llm_model="test-model",
                rate_limit_per_min=0, workers=2, job_timeout_s=120.0, retention_days=14, render_preview=True, design_attempts=3, review_rounds=1,
                design_timeout_s=40.0, trust_proxy=False, slicer="off")
    base.update(over)
    return Settings(**base)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def make_client(tmp_path):
    """Factory: a TestClient with custom settings and an optional scripted model."""
    opened = []

    def factory(llm=None, **over):
        c = TestClient(create_app(make_settings(tmp_path, **over), llm_client=llm))
        c.__enter__()
        opened.append(c)
        return c
    yield factory
    for c in opened:
        c.__exit__(None, None, None)
