from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..deps import get_conn, get_current_user, public_item

router = APIRouter(prefix="/items", tags=["items"])


class ItemCreate(BaseModel):
    title: str
    description: str = ""


@router.get("/")
def list_items(user=Depends(get_current_user), conn=Depends(get_conn)):
    owner_id = None if user["is_superuser"] else user["id"]
    return [public_item(i) for i in db.list_items(conn, owner_id)]


@router.post("/", status_code=201)
def create_item(payload: ItemCreate, user=Depends(get_current_user), conn=Depends(get_conn)):
    if not payload.title.strip():
        raise HTTPException(status_code=422, detail="Title must not be empty")
    return public_item(db.create_item(conn, payload.title.strip(), payload.description, user["id"]))


@router.get("/{item_id}")
def read_item(item_id: int, user=Depends(get_current_user), conn=Depends(get_conn)):
    item = db.get_item(conn, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item["owner_id"] != user["id"] and not user["is_superuser"]:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return public_item(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, user=Depends(get_current_user), conn=Depends(get_conn)):
    item = db.get_item(conn, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item["owner_id"] != user["id"] and not user["is_superuser"]:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    db.delete_item(conn, item_id)
