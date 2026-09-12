from datetime import timedelta, datetime
from uuid import uuid4
import jwt as pyjwt
from fastapi import HTTPException, Request

from database.config.config import settings
from utils.load_setting_keys import load_keys

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
FERNET_SECRET_KEY = settings.FERNET_SECRET_KEY
ALGORITHM = settings.ALGORITHM
PRIVATE_KEY, PUBLIC_KEY = load_keys(settings)

def create_token(data: dict, expires_delta: timedelta) -> str:
    try:
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        token = pyjwt.encode(to_encode, PRIVATE_KEY, algorithm=ALGORITHM)
        return token

    except TypeError as e:
        # For non-serializable data in payload
        raise HTTPException(status_code=400, detail=f"Invalid data in payload: {str(e)}")

    except pyjwt.PyJWTError as e:
        # Any JWT-specific errors from PyJWT
        raise HTTPException(status_code=500, detail=f"Token creation error: {str(e)}")

    except Exception as e:
        # Catch-all for unexpected errors
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")



def decode_token(token: str) -> dict:
    try:
        # Attempt to decode the JWT token
        return pyjwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])

    except pyjwt.ExpiredSignatureError:
        # Token has expired
        raise HTTPException(status_code=401, detail="Token has expired")

    except pyjwt.InvalidSignatureError:
        # Signature does not match
        raise HTTPException(status_code=401, detail="Invalid token signature")
    except pyjwt.DecodeError:
        # Failed to decode token (corrupted or malformed)
        raise HTTPException(status_code=401, detail="Failed to decode token")
    except pyjwt.InvalidTokenError:
        # Catch any other invalid token issues
        raise HTTPException(status_code=401, detail="Invalid token")

    except Exception as e:
        # Catch-all for any other unexpected exceptions
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


def create_access_token(data: dict) -> str:
    return create_token(data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(data: dict):
    jti = str(uuid4())
    exp = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token_data = {**data, "jti": jti}
    token = create_token(token_data, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    return token, jti, exp


def get_access_token_from_header(request: Request) -> str:
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return token.strip()