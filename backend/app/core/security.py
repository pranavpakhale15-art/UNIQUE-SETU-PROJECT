from datetime import datetime, timedelta, timezone
import hashlib, secrets
import jwt
from argon2 import PasswordHasher
from app.core.config import settings

password_hasher = PasswordHasher()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except Exception:
        return False

def _jwt_secret() -> str:
    secret = settings.jwt_secret_key
    if len(secret.strip()) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters")
    return secret

def create_token(subject: str, token_type: str, expires_delta: timedelta, jti: str | None = None,
                 session_id: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + expires_delta,
               "jti": jti or secrets.token_urlsafe(24)}
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid or expired token") from exc

def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def new_refresh_token_id() -> str:
    return secrets.token_urlsafe(32)
