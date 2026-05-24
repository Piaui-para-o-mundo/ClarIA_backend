from fastapi.testclient import TestClient

import app.core.database as _db


async def _noop():
    return None


_db.init_db = _noop
_db.close_db = _noop

from src.main import create_app


app = create_app()
client = TestClient(app)


def test_dispatch_preview_renders_html():
    payload = {
        "setor_destino_sugerido": "DGP/DAOS",
        "assunto": "Progressão Funcional",
        "corpo_despacho": "DESPACHO\nLinha 2",
        "referencias_normativas": ["Regulamento de Progressão Funcional da UESPI"],
        "justificativa_encaminhamento": "Pendencias documentais identificadas.",
        "status_sugerido": "devolvido",
    }

    response = client.post("/api/v1/dispatch/preview", json=payload)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Progressão Funcional" in response.text
    assert "DGP/DAOS" in response.text
    assert "Pendencias documentais identificadas." in response.text