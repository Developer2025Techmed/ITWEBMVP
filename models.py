from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

# --- User Models ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8) # Security: Input validation for password length
    name: str = Field(min_length=2, max_length=50)

class UserLogin(BaseModel):
    email: EmailStr # Using email as the username for login
    password: str

class UserResponse(BaseModel): # For returning user info safely (e.g., /users/me)
    id: str
    email: EmailStr
    name: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# --- Token Data Model (used internally in auth.py) ---
class TokenData(BaseModel):
    email: Optional[EmailStr] = None
    user_id: Optional[str] = None


# --- Translation Models (already defined, but good to see context) ---
class TranslationSession(BaseModel):
    id: Optional[str] = Field(alias="_id", default=None)
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    original_text: str
    translated_text: str
    source_language: Optional[str] = "English"
    target_language: Optional[str] = "isiZulu"

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: Optional[str] = None
    target_language: Optional[str] = None

# (Other models like AudioUploadMetadata if used would also be here)
