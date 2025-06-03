# auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId # For MongoDB ObjectId handling

# Import settings from config.py (assuming config.py is in the same directory)
from config import settings

# --- JWT Configuration ---
ALGORITHM = "HS256"
# Use from settings if defined there, otherwise use a default
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES', 30)

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
# tokenUrl should point to your login endpoint (e.g., /auth/login)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login") # Adjust if your login route is different

# --- Pydantic Models for Token Data and User in DB ---
class TokenData(BaseModel):
    email: Optional[EmailStr] = None
    user_id: Optional[str] = None # Expecting user_id as string in token

class UserInDB(BaseModel):
    """ User model as it's represented in the database (for internal use). """
    id: str = Field(..., alias="_id") # MongoDB's _id field, aliased to 'id'
    email: EmailStr
    name: str
    hashed_password: str
    # Add other fields you store for a user if needed

    class Config:
        populate_by_name = True # Allow using alias _id for id field
        from_attributes = True  # Allow creating from object attributes (ORM mode)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token using data from the user."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    # Use JWT_SECRET_KEY from the imported settings object
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request, token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    """
    Decodes JWT, validates it, and fetches the raw user dictionary from DB.
    Used as a dependency for get_current_active_user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("email")
        user_id_from_token: Optional[str] = payload.get("user_id") # ID from token payload

        if email is None or user_id_from_token is None:
            raise credentials_exception
        if not ObjectId.is_valid(user_id_from_token): # Validate before converting
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    db = request.app.database # Access database from the FastAPI app instance via request

    # Fetch user by ObjectId and email for robust checking
    user = await db["users"].find_one({"_id": ObjectId(user_id_from_token), "email": email})

    if user is None:
        raise credentials_exception
    return user # Return the raw user dictionary

async def get_current_active_user(
    current_user_dict: Annotated[dict, Depends(get_current_user)]
) -> UserInDB:
    """
    Validates the raw user dictionary from DB against UserInDB Pydantic model.
    This is the dependency typically used in protected routes.
    """
    # Ensure _id is a string for Pydantic model validation
    if "_id" in current_user_dict and isinstance(current_user_dict["_id"], ObjectId):
        current_user_dict["_id"] = str(current_user_dict["_id"])

    try:
        user = UserInDB(**current_user_dict)
    except Exception as e: # Catch Pydantic validation errors
        # For debugging:
        # print(f"Error creating UserInDB model from dict: {current_user_dict}, Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User data from token is invalid or malformed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # You might add checks here like user.disabled if you have such a field
    return user
