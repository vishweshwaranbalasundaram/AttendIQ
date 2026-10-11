"""JWT login + role guards."""
import datetime as dt

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from attendiq import config

_bearer = HTTPBearer(auto_error=False)


def create_token(user: dict) -> str:
    payload = {"sub": user["username"], "role": user["role"], "linked_id": user["linked_id"],
               "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=config.TOKEN_HOURS)}
    return jwt.encode(payload, config.SECRET, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    try:
        data = jwt.decode(creds.credentials, config.SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    return {"username": data["sub"], "role": data["role"], "linked_id": data.get("linked_id")}


def require(*roles):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, f"Requires role: {', '.join(roles)}")
        return user
    return dep
