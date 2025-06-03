from fastapi import APIRouter, Depends, HTTPException, status, Request
# from fastapi.security import OAuth2PasswordRequestForm # Use if you prefer form data for login
from datetime import timedelta
from typing import Annotated # For Python 3.9+ type hinting for Depends

from models import UserCreate, UserLogin, Token, UserResponse # Pydantic models
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_active_user, # Example for a protected route
    UserInDB # For type hinting current_user
)
from bson import ObjectId # For creating MongoDB ObjectId

router = APIRouter()

@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(request: Request, user_create: UserCreate):
    """
    Signs up a new user:
    - Validates input using UserCreate Pydantic model.
    - Checks if email already exists.
    - Hashes the password using bcrypt.
    - Stores user in MongoDB with an ObjectId.
    - Returns a JWT access token.
    """
    db = request.app.database
    existing_user = await db["users"].find_one({"email": user_create.email})
    if existing_user:
        # Security: Prevent duplicate email registrations.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    hashed_password = get_password_hash(user_create.password)

    # Create a new BSON ObjectId for the user
    user_id_obj = ObjectId()

    user_db_data = {
        "_id": user_id_obj, # Store as ObjectId
        "email": user_create.email,
        "name": user_create.name,
        "hashed_password": hashed_password,
        # "created_at": datetime.now(timezone.utc) # Optional: timestamp
    }

    # Insert new user into the database
    await db["users"].insert_one(user_db_data)

    # Create access token. 'user_id' in token data should be the string representation of ObjectId.
    access_token = create_access_token(
        data={"email": user_create.email, "user_id": str(user_id_obj)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/login", response_model=Token)
async def login(request: Request, form_data: UserLogin): # Using UserLogin model for JSON body
    """
    Logs in an existing user:
    - Validates input using UserLogin Pydantic model.
    - Fetches user by email.
    - Verifies password against the stored hash.
    - Returns a JWT access token.
    Security: bcrypt protects against timing attacks during password verification.
    """
    db = request.app.database
    user_dict = await db["users"].find_one({"email": form_data.email})

    if not user_dict or not verify_password(form_data.password, user_dict["hashed_password"]):
        # Security: Generic error for incorrect email or password to avoid user enumeration.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}, # Part of OAuth2 standard
        )

    user_id_str = str(user_dict["_id"]) # Convert ObjectId to string for JWT

    access_token = create_access_token(
        data={"email": user_dict["email"], "user_id": user_id_str},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, token_type="bearer")

# Example of a protected route (could be in a different router file e.g., user_routes.py)
@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: Annotated[UserInDB, Depends(get_current_active_user)]):
    """
    Fetches the current authenticated user's details (excluding sensitive info like password).
    Security: Requires a valid JWT, provided by `get_current_active_user` dependency.
    """
    # current_user is of type UserInDB, map to UserResponse
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name
    )
