import os
import shutil # For file operations if needed, though less direct need with UploadFile
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request, Form
from fastapi.concurrency import run_in_threadpool # If any synchronous I/O heavy part not covered by clients

from models import TranslationSession, TranslationResponse # Pydantic models
from auth import get_current_active_user, UserInDB # Authentication
from utils.whisper_client import transcribe_audio # AI client
from utils.gpt_client import translate_text # AI client

router = APIRouter()

# Configuration for file uploads
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_AUDIO_CONTENT_TYPES = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/webm", "audio/m4a", "audio/ogg", "audio/aac"]


@router.post("/translate", response_model=TranslationResponse)
async def create_translation_session_route(
    request: Request, # No default
    current_user: Annotated[UserInDB, Depends(get_current_active_user)], # No default (provided by Depends)
    # --- Now parameters with defaults ---
    text_input: Annotated[Optional[str], Form()] = None,
    audio_file: Annotated[Optional[UploadFile], File()] = None,
    target_language_form: Annotated[Optional[str], Form()] = None,
    source_language_form: Annotated[Optional[str], Form()] = None
):
    # ... rest of the function
    """
    Handles translation requests. Accepts either an audio file for transcription
    followed by translation, or direct text input for translation.

    - Requires JWT authentication.
    - Validates inputs (file type, size, presence of at least one input type).
    - Uses Whisper for transcription (if audio provided).
    - Uses GPT for translation.
    - Stores the original text and translated text in MongoDB.
    """
    db = request.app.database
    original_text_to_process: str = ""

    # --- Input Validation: Ensure at least one input type is provided ---
    if not audio_file and not (text_input and text_input.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either an audio file ('audio_file') or text input ('text_input') must be provided."
        )

    # --- Determine target and source languages ---
    # Priority: Form data > Defaults in gpt_client.py
    # For MVP, we'll primarily rely on defaults in gpt_client for simplicity now
    # but show how they could be overridden.
    effective_target_language = target_language_form if target_language_form else "isiZulu" # Default in gpt_client can also handle this
    effective_source_language = source_language_form # Pass None if not provided, gpt_client handles optional

    temp_audio_path: Optional[str] = None # Path for temporarily storing uploaded audio

    try:
        # --- Process Audio Input (if provided) ---
        if audio_file:
            if not audio_file.content_type or audio_file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid audio file type: {audio_file.content_type}. Supported: {', '.join(ALLOWED_AUDIO_CONTENT_TYPES)}"
                )

            # Create a temporary file to save the upload
            # This is important as Whisper client expects a file path.
            # Security: Generate a unique temp filename to avoid conflicts.
            # Ensure this temp directory is secure and cleaned up.
            # FastAPI's UploadFile.file is a SpooledTemporaryFile.

            temp_dir = "temp_audio_files" # Make sure this directory exists or is handled properly
            os.makedirs(temp_dir, exist_ok=True) # Ensure temp dir exists
            # Sanitize filename from client if using it, or generate a new one.
            safe_filename = f"{current_user.id}_{datetime.now().timestamp()}_{audio_file.filename if audio_file.filename else 'audio.tmp'}"
            # Limit filename length and character set if necessary.
            temp_audio_path = os.path.join(temp_dir, safe_filename)

            file_size = 0
            with open(temp_audio_path, "wb") as buffer:
                # Read file in chunks to check size and save
                while chunk := await audio_file.read(1024 * 1024): # Read 1MB chunks
                    file_size += len(chunk)
                    if file_size > MAX_FILE_SIZE_BYTES:
                        # Clean up oversized file immediately
                        buffer.close() # Close file before attempting to remove
                        os.remove(temp_audio_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Audio file too large. Maximum size is {MAX_FILE_SIZE_MB}MB."
                        )
                    buffer.write(chunk)

            if file_size == 0:
                os.remove(temp_audio_path) # Clean up empty file
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Audio file is empty."
                )

            # 1. Transcribe audio using Whisper client
            transcribed_text_from_audio = await transcribe_audio(
                file_path=temp_audio_path,
                language=effective_source_language if effective_source_language else "en" # Whisper benefits from knowing source lang
            )

            if not transcribed_text_from_audio or transcribed_text_from_audio.startswith("Transcription service unavailable") or transcribed_text_from_audio.startswith("Transcription failed"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Transcription failed or service unavailable: {transcribed_text_from_audio}"
                )
            original_text_to_process = transcribed_text_from_audio.strip()

        # --- Process Text Input (if provided and no audio took precedence) ---
        elif text_input and text_input.strip():
            original_text_to_process = text_input.strip()

        else: # Should not happen due to initial check, but as a safeguard
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid input provided.")


        # --- Perform Translation ---
        if not original_text_to_process: # If after all processing, text is still empty
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text to translate cannot be empty after processing input.")

        translated_text_from_gpt = await translate_text(
            text_to_translate=original_text_to_process,
            target_language=effective_target_language,
            source_language=effective_source_language
        )

        if not translated_text_from_gpt or translated_text_from_gpt.startswith("Translation service unavailable") or translated_text_from_gpt.startswith("Translation failed"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Translation failed or service unavailable: {translated_text_from_gpt}"
            )

        # --- Store session in MongoDB ---
        session_data = TranslationSession(
            user_id=str(current_user.id), # current_user.id is already string from UserInDB
            timestamp=datetime.now(tz=None), # Store naive datetime, or ensure timezone consistency
            original_text=original_text_to_process,
            translated_text=translated_text_from_gpt,
            source_language=effective_source_language if effective_source_language else "auto-detected", # Or get from Whisper/GPT if they return it
            target_language=effective_target_language
        )

        await db["sessions"].insert_one(session_data.model_dump(by_alias=True, exclude_none=True))

        return TranslationResponse(
            original_text=original_text_to_process,
            translated_text=translated_text_from_gpt,
            source_language=session_data.source_language,
            target_language=session_data.target_language
        )

    except HTTPException:
        # Re-raise HTTPExceptions to let FastAPI handle them
        raise
    except Exception as e:
        # Security: Log the full error for backend debugging.
        print(f"Unexpected error in translation route: {type(e).__name__} - {e}")
        # Return a generic error to the client.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the translation process."
        )
    finally:
        # --- Cleanup: Remove temporary audio file ---
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception as e_remove:
                print(f"Error removing temporary file {temp_audio_path}: {e_remove}")
        if audio_file:
            await audio_file.close()
