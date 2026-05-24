from app.core.security import hash_password, verify_password, create_access_token, decode_token


def test_hash_and_verify():
    pw = "strong_password_123"
    h = hash_password(pw)
    assert verify_password(pw, h)


def test_jwt_create_and_decode():
    token = create_access_token({"sub": "test-sub"})
    payload = decode_token(token)
    assert payload.get("sub") == "test-sub"
