from fastapi import Depends, Header, HTTPException

from . import db
from .security import decode_access_token


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def get_current_user(
    conn=Depends(get_conn),
    authorization: str = Header(default=""),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get_user(conn, int(payload["sub"]))
    if user is None or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Inactive or missing user")
    return user


def get_current_superuser(user=Depends(get_current_user)):
    if not user["is_superuser"]:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return user


def public_user(user):
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "is_active": bool(user["is_active"]),
        "is_superuser": bool(user["is_superuser"]),
    }


def public_item(item):
    return {
        "id": item["id"],
        "title": item["title"],
        "description": item["description"],
        "owner_id": item["owner_id"],
    }
