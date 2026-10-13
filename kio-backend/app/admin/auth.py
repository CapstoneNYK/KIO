import os
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator

from app.admin import db

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12시간

ADMIN_SIGNUP_CODE = os.getenv("ADMIN_SIGNUP_CODE", "")

_bearer_scheme = HTTPBearer(auto_error=False)
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{4,20}$")


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    password: str
    signup_code: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("아이디는 영문/숫자/-/_ 4~20자로 입력해주세요.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_admin_credentials(username: str, password: str) -> bool:
    admin = db.get_admin_by_username(username)
    if admin is None:
        return False
    return bcrypt.checkpw(password.encode(), admin["password_hash"].encode())


def register_admin(body: SignupRequest) -> None:
    if not ADMIN_SIGNUP_CODE or body.signup_code != ADMIN_SIGNUP_CODE:
        raise HTTPException(status_code=403, detail="가입 코드가 올바르지 않습니다.")
    if db.get_admin_by_username(body.username) is not None:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    db.create_admin(body.username, password_hash)


def create_access_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 토큰입니다.",
        )
    return payload["sub"]
