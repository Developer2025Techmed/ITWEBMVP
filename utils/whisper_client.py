import os
from openai import AsyncOpenAI
import httpx

# --- Environment Variables ---
# Security: OPENAI_API_KEY is loaded from environment variables.
# This key should have the minimum necessary permissions for Whisper and GPT services.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    # In a real application, this might raise a specific configuration error.
    # For MVP development, a print statement and a default (weak) key might be used cautiously,
    # but it's better to ensure the key is always set.
    print("CRITICAL: OPENAI_API_KEY environment variable not set. AI services will fail.")
    # Forcing a failure if not set is safer than using a default weak key.
    # raise EnvironmentError("OPENAI_API_KEY must be set for AI services to function.")

# Initialize the AsyncOpenAI client
# It's good practice to use a custom HTTP client for configuring retries, timeouts, etc.
# For MVP, default AsyncOpenAI client with a basic timeout is acceptable.
# Security: Ensure network requests to OpenAI are over HTTPS (default for the library).
aclient_http_options = {"timeout": 60.0} # 60 seconds timeout for OpenAI calls
if OPENAI_API_KEY: # Only initialize if key is present
    aclient = AsyncOpenAI(api_key=OPENAI_API_KEY, http_client=httpx.AsyncClient(**aclient_http_options))
else:
    aclient = None # Client remains None if API key is not set

async def transcribe_audio(file_path: str, language: str = "en") -> str:
    """
    Transcribes audio from a given file path using OpenAI Whisper API.

    Args:
        file_path (str): The path to the audio file.
        language (str, optional): The language of the audio. Defaults to "en" (English).
                                  Specifying language can improve accuracy. ISO 639-1 format.
    Returns:
        str: The transcribed text. Returns an empty string if transcription fails or
             if the client is not initialized (due to missing API key).
    Raises:
        Exception: Can re-raise exceptions from the OpenAI client for critical errors,
                   or handle them and return empty/error string.
    """
    if not aclient:
        print("Error: OpenAI client not initialized. Cannot transcribe audio.")
        return "Transcription service unavailable: API key missing." # Or empty string

    try:
        with open(file_path, "rb") as audio_file_object:
            # Security: The 'audio_file_object' is passed to the OpenAI library,
            # which handles the secure transmission of this data.
            # Ensure the file path provided is trusted and validated before this point
            # to prevent directory traversal or unauthorized file access if 'file_path'
            # were ever constructed from user input directly without sanitization (not the case here).

            # Using the 'transcriptions' endpoint with 'whisper-1' model.
            transcript_response = await aclient.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file_object, # Pass the file object
                language=language,       # Optional: helps Whisper if language is known
                response_format="text"   # Request plain text directly
            )

        # The response for "text" format is directly the string of the transcript.
        transcribed_text = str(transcript_response).strip()
        return transcribed_text

    except httpx.ReadTimeout:
        print(f"Error calling OpenAI Whisper API: ReadTimeout after {aclient_http_options['timeout']} seconds.")
        return "Transcription timed out." # Specific user-friendly message
    except Exception as e:
        # Security: Log the full error 'e' for debugging on the backend.
        # Avoid returning raw error messages from external services directly to the client if they might contain sensitive info.
        print(f"Error calling OpenAI Whisper API: {type(e).__name__} - {e}")
        # Return a generic error message or an empty string.
        return "Transcription failed." # Or empty string ""
