# app.py
import os
from dotenv import load_dotenv

# Load .env variables before other imports if any direct os.getenv calls are made early.
# config.py also calls load_dotenv(), so this might be redundant if config is imported first
# and no os.getenv() is used before settings from config.py are available.
# However, it's harmless to call it multiple times; first one wins for each variable.
load_dotenv()

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware # Import the middleware class
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient

# Import settings from your config.py file
from config import settings

# Import your route modules
from routes import auth_routes, translation_routes # Assuming these exist

# --- Initialize FastAPI App ---
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Backend services for the Bilingual AI Healthcare Translation App (BUA)."
)

# --- Database Connection Events ---
@app.on_event("startup")
async def startup_db_client():
    try:
        app.mongodb_client = AsyncIOMotorClient(settings.MONGO_URI)
        app.database = app.mongodb_client.bua_db # Or your specific database name
        # Test connection
        await app.mongodb_client.admin.command('ping')
        print(f"Successfully connected to MongoDB using URI: ...{settings.MONGO_URI[-30:]}") # Print partial URI for confirmation

        # Example: Ensure indexes (idempotent operation)
        await app.database["users"].create_index("email", unique=True)
        print("Ensured 'email' index on 'users' collection.")

    except Exception as e:
        print(f"CRITICAL: Failed to connect to MongoDB or perform startup operations: {e}")
        # You might want to raise the exception or exit if DB connection is critical for startup
        # For now, it will just print the error.
        app.mongodb_client = None # Ensure it's None if connection failed
        app.database = None


@app.on_event("shutdown")
async def shutdown_db_client():
    if hasattr(app, 'mongodb_client') and app.mongodb_client:
        app.mongodb_client.close()
        print("Disconnected from MongoDB.")

# --- CORS Middleware ---
# Ensure CORSMiddleware is the first argument to app.add_middleware
app.add_middleware(
    CORSMiddleware,  # This is the middleware_class
    allow_origins=[settings.ALLOWED_ORIGIN] if settings.ALLOWED_ORIGIN else ["*"], # From settings
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- Include Routers ---
# Ensure your route files (auth_routes.py, translation_routes.py) exist in a 'routes' directory
# and correctly define their APIRouter instances named 'router'.
app.include_router(auth_routes.router, tags=["Authentication"], prefix="/auth")
app.include_router(translation_routes.router, tags=["Translation"], prefix=settings.API_PREFIX)


# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}!"}

# --- General Exception Handler (Optional but Recommended) ---
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log the exception for debugging purposes
    # import traceback
    # print(f"Unhandled error for request {request.url}:\n{traceback.format_exc()}")
    print(f"Unhandled error for request {request.url}: {exc}") # Simpler log
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )
