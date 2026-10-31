from app.core.security import hash_password, verify_password, create_token, decode_token
from app.core.config import Settings, settings
from datetime import timedelta
import pytest
from pydantic import ValidationError

def test_password_hashing():
    hashed=hash_password("CorrectHorse9Battery")
    assert hashed != "CorrectHorse9Battery"
    assert verify_password("CorrectHorse9Battery",hashed)
    assert not verify_password("wrong",hashed)

def test_token_roundtrip():
    token=create_token("507f1f77bcf86cd799439011","access",timedelta(minutes=1))
    assert decode_token(token)["sub"]=="507f1f77bcf86cd799439011"

def test_jwt_secret_is_required_in_all_environments():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be at least 32 characters"):
        Settings(app_env="development", jwt_secret_key="too-short")

def test_token_creation_does_not_fall_back_to_a_default_secret(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be at least 32 characters"):
        create_token("507f1f77bcf86cd799439011", "access", timedelta(minutes=1))
