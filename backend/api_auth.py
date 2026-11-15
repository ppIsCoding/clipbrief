from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import (
    create_token,
    get_current_user,
    hash_password,
    validate_email,
    validate_password,
    verify_password,
)
from database import create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _build_user_response(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
    }


def normalize_email(email: str) -> str:
    """邮箱统一小写去空格，避免大小写导致重复账号。"""
    return (email or "").strip().lower()


@router.post("/register")
async def register(req: RegisterRequest):
    email = normalize_email(req.email)
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    err = validate_password(req.password)
    if err:
        raise HTTPException(status_code=400, detail=err)

    if get_user_by_email(email):
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    hashed = hash_password(req.password)
    user = create_user(email, hashed)
    token = create_token(user["id"], email)

    return {
        "success": True,
        "data": {
            "token": token,
            "user": {"id": user["id"], "email": email},
        },
    }


@router.post("/login")
async def login(req: LoginRequest):
    email = normalize_email(req.email)
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="邮箱或密码错误")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")

    token = create_token(user["id"], user["email"])
    return {
        "success": True,
        "data": {
            "token": token,
            "user": _build_user_response(user),
        },
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "data": _build_user_response(user),
    }
