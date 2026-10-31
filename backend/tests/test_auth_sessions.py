from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException, Response
from pydantic import ValidationError
from starlette.requests import Request

from app.api.v1 import auth
from app.api.v1.auth import refresh
from app.core.security import token_digest
from app.schemas.auth import LoginRequest, RefreshRequest


class SessionCollection:
    def __init__(self, sessions):
        self.documents = sessions

    def find_one(self, query):
        for document in self.documents:
            matches = True
            for field, expected in query.items():
                actual = document.get(field)
                if isinstance(expected, dict) and "$gt" in expected:
                    matches = actual is not None and actual > expected["$gt"]
                else:
                    matches = actual == expected
                if not matches:
                    break
            if matches:
                return document.copy()
        return None

    def insert_one(self, document):
        self.documents.append(document.copy())
        return SimpleNamespace(inserted_id=document["_id"])

    def update_one(self, query, update):
        document = self.find_one(query)
        if not document:
            return SimpleNamespace(modified_count=0)
        stored = next(item for item in self.documents if item["_id"] == document["_id"])
        stored.update(update["$set"])
        return SimpleNamespace(modified_count=1)


class UserCollection:
    def __init__(self, user):
        self.user = user

    def find_one(self, query):
        if all(self.user.get(key) == value for key, value in query.items()):
            return self.user.copy()
        return None


class FakeDatabase:
    def __init__(self, user, sessions):
        self.users = UserCollection(user)
        self.sessions = SessionCollection(sessions)


class LoginUsers:
    def __init__(self, user):
        self.user = user

    def find_one(self, query):
        if self.user.get("normalized_mobile_number") == query.get("normalized_mobile_number"):
            return self.user.copy()
        return None

    def update_one(self, query, update):
        self.user.update(update["$set"])


class LoginSessions:
    def insert_one(self, document):
        return SimpleNamespace(inserted_id=document["_id"])


class LoginDatabase:
    def __init__(self, user):
        self.users = LoginUsers(user)
        self.sessions = LoginSessions()


def make_request():
    return Request({"type": "http", "method": "POST", "path": "/api/v1/auth/refresh",
                    "headers": [(b"user-agent", b"session-test")], "query_string": b""})


def test_refresh_rotates_and_revokes_the_previous_session():
    user_id = ObjectId()
    session_id = ObjectId()
    old_refresh = "old-refresh-token"
    now = datetime.now(timezone.utc)
    old_session = {"_id": session_id, "user_id": user_id, "refresh_token_hash": token_digest(old_refresh),
                   "expires_at": now + timedelta(hours=1), "revoked": False}
    database = FakeDatabase({"_id": user_id, "account_status": "active"}, [old_session])
    response = Response()

    result = refresh(RefreshRequest(refresh_token=old_refresh), make_request(), response, database)

    assert result == {"token_type": "cookie"}
    assert database.sessions.documents[0]["revoked"] is True
    assert database.sessions.documents[1]["refresh_token_hash"] != old_refresh
    assert database.sessions.documents[1]["user_agent"] == "session-test"
    with pytest.raises(HTTPException) as error:
        refresh(RefreshRequest(refresh_token=old_refresh), make_request(), Response(), database)
    assert error.value.status_code == 401


@pytest.mark.parametrize("account_type", ["customer", "staff", "owner", "admin"])
def test_login_accepts_matching_selected_account_type(monkeypatch, account_type):
    user_id = ObjectId()
    user = {
        "_id": user_id,
        "normalized_mobile_number": "8149921445",
        "password_hash": "test-hash",
        "account_status": "active",
        "role": account_type,
    }
    database = LoginDatabase(user)
    response = Response()
    monkeypatch.setattr(auth, "consume_login_attempt", lambda *_args: True)
    monkeypatch.setattr(auth, "verify_password", lambda *_args: True)

    result = auth.login(
        LoginRequest(mobile_number="8149921445", password="test-password", account_type=account_type),
        make_request(),
        response,
        database,
    )

    assert result["user"]["role"] == account_type
    assert any(name == b"set-cookie" for name, _ in response.raw_headers)


def test_login_rejects_a_different_selected_account_type(monkeypatch):
    user = {
        "_id": ObjectId(),
        "normalized_mobile_number": "8149921445",
        "password_hash": "test-hash",
        "account_status": "active",
        "role": "owner",
    }
    database = LoginDatabase(user)
    response = Response()
    monkeypatch.setattr(auth, "consume_login_attempt", lambda *_args: True)
    monkeypatch.setattr(auth, "verify_password", lambda *_args: True)

    with pytest.raises(HTTPException) as error:
        auth.login(
            LoginRequest(mobile_number="8149921445", password="test-password", account_type="customer"),
            make_request(),
            response,
            database,
        )

    assert error.value.status_code == 401
    assert not any(name == b"set-cookie" for name, _ in response.raw_headers)


def test_login_rejects_unsupported_account_type():
    with pytest.raises(ValidationError):
        LoginRequest(mobile_number="8149921445", password="test-password", account_type="superuser")
