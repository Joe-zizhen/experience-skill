from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from .. import db
from ..deps import get_conn, get_current_superuser, get_current_user, public_user

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class UserUpdateMe(BaseModel):
    full_name: str


@router.get("/")
def list_users(user=Depends(get_current_superuser), conn=Depends(get_conn)):
    return [public_user(u) for u in db.list_users(conn)]


@router.post("/", status_code=201)
def create_user(payload: UserCreate, user=Depends(get_current_superuser), conn=Depends(get_conn)):
    if db.get_user_by_email(conn, payload.email) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password too short")
    return public_user(db.create_user(conn, payload.email, payload.password, payload.full_name))


@router.get("/me")
def read_me(user=Depends(get_current_user)):
    return public_user(user)


@router.patch("/me")
def update_me(payload: UserUpdateMe, user=Depends(get_current_user), conn=Depends(get_conn)):
    return public_user(db.update_user_full_name(conn, user["id"], payload.full_name))
