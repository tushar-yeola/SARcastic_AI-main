from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db, engine
from backend.core.config import settings
from backend.core.security import oauth2_scheme
from backend.models.auth_models import Token

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception
    
    # Check user in DB
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT * FROM users WHERE username = :u"), {"u": username}
        ).fetchone() # Mapping result for dict access? Fetchone returns Row or Tuple depending on engine setup.
    
    if user is None:
        raise credentials_exception
    return user
