from fastapi.testclient import TestClient

import app.core.database as _db

# prevent real DB init/close during tests
async def _noop():
    return None

_db.init_db = _noop
_db.close_db = _noop

from src.main import create_app

app = create_app()
client = TestClient(app)


def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("status") == "ok"
