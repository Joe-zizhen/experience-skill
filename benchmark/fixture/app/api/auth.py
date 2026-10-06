from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from .. import db
from ..deps import get_conn
from ..security import create_access_token, verify_password

router = APIRouter(tags=["auth"])


@router.post("/login/access-token")
def login(form: OAuth2PasswordRequestForm = Depends(), conn=Depends(get_conn)):
    user = db.get_user_by_email(conn, form.username)
    if user is None or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return {"access_token": create_access_token(user["id"]), "token_type": "bearer"}
