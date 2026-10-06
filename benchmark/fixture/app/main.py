from fastapi import FastAPI

from .api import auth, health, items, users

app = FastAPI(title="benchfix")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(items.router)
app.include_router(health.router)
