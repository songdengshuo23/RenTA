import importlib
import sys

from fastapi.testclient import TestClient


MODULE_PREFIX = "acps_ca_challenge"


def load_test_app(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    challenge_dir = tmp_path / "challenges"
    env_file.write_text(
        "UVICORN_HOST=127.0.0.1\n"
        "UVICORN_PORT=8004\n"
        "UVICORN_RELOAD=false\n"
        f"CHALLENGE_DIR={challenge_dir}\n"
        "LOG_LEVEL=INFO\n"
        "BASE_URL=/acps-atr-v2\n"
        "CHALLENGE_WRITE_TOKEN=test-challenge-token\n"
        "MAX_CHALLENGE_BYTES=64\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV_FILE", str(env_file))

    for name in list(sys.modules):
        if name == MODULE_PREFIX or name.startswith(f"{MODULE_PREFIX}."):
            sys.modules.pop(name)

    module = importlib.import_module("acps_ca_challenge.main")
    return module.app


def test_challenge_post_requires_token(tmp_path, monkeypatch):
    client = TestClient(load_test_app(tmp_path, monkeypatch))
    resp = client.post(
        "/acps-atr-v2/1.2.156.3088.0001.00001.E48YMP.8C14DT.1.0R4Y/token",
        content="payload",
    )
    assert resp.status_code == 401


def test_challenge_post_rejects_bad_token(tmp_path, monkeypatch):
    client = TestClient(load_test_app(tmp_path, monkeypatch))
    resp = client.post(
        "/acps-atr-v2/1.2.156.3088.0001.00001.E48YMP.8C14DT.1.0R4Y/token",
        content="payload",
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 403


def test_challenge_post_accepts_valid_token_and_get_remains_public(tmp_path, monkeypatch):
    client = TestClient(load_test_app(tmp_path, monkeypatch))
    url = "/acps-atr-v2/1.2.156.3088.0001.00001.E48YMP.8C14DT.1.0R4Y/token"
    resp = client.post(
        url,
        content="payload",
        headers={"Authorization": "Bearer test-challenge-token"},
    )
    assert resp.status_code == 200

    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.text == "payload"


def test_challenge_post_rejects_oversized_body(tmp_path, monkeypatch):
    client = TestClient(load_test_app(tmp_path, monkeypatch))
    resp = client.post(
        "/acps-atr-v2/1.2.156.3088.0001.00001.E48YMP.8C14DT.1.0R4Y/token",
        content="x" * 65,
        headers={"Authorization": "Bearer test-challenge-token"},
    )
    assert resp.status_code == 413
