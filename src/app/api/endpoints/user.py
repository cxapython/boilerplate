from fastapi import Depends
from starlette_auth.tables import User
from starlette_core.database import Session

from .. import schemas
from ..main import app
from ..oauth import get_oauth_user


@app.get("/users/me", response_model=schemas.User)
async def read_user_me(current_user: User = Depends(get_oauth_user)):
    return current_user
