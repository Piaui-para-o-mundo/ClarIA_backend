from io import BytesIO

from fastapi import File, Form, UploadFile
from fastapi.testclient import TestClient

from src.main import _sanitize_validation_payload, create_app


def test_sanitize_validation_payload_replaces_binary_values():
    payload = {
        "detail": [
            {"input": b"\xff\x00", "loc": ("body", "files")},
            {"input": [b"bin", {"nested": bytearray(b"raw")}], "loc": ("body", "type_process")},
        ]
    }

    sanitized = _sanitize_validation_payload(payload)

    assert sanitized["detail"][0]["input"] == "<binary payload omitted>"
    assert sanitized["detail"][1]["input"][0] == "<binary payload omitted>"
    assert sanitized["detail"][1]["input"][1]["nested"] == "<binary payload omitted>"


def test_request_validation_uses_sanitized_422_response():
    app = create_app()

    @app.post("/validation-demo")
    async def validation_demo(
        files: list[UploadFile] = File(...),
        type_process: str = Form(...),
    ):
        return {"files": len(files), "type_process": type_process}

    client = TestClient(app)

    response = client.post(
        "/validation-demo",
        files=[("files", ("doc.pdf", BytesIO(b"%PDF-1.4\n\xff\xfe"), "application/pdf"))],
    )

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body