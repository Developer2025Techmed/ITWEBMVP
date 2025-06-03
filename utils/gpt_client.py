import os
from openai import AsyncOpenAI
import httpx
from typing import Optional # For Optional type hint

# --- Environment Variables ---
# Security: OPENAI_API_KEY is loaded from environment variables.
# This key should have the minimum necessary permissions for Whisper and GPT services.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Already loaded in whisper_client, but good for module independence

if not OPENAI_API_KEY:
    print("CRITICAL: OPENAI_API_KEY environment variable not set. AI services will fail.")
    # As with whisper_client, ensure this doesn't proceed with a non-functional client.
    # raise EnvironmentError("OPENAI_API_KEY must be set for AI services to function.")

# Initialize the AsyncOpenAI client (can share with whisper_client if refactored, or keep separate)
# For module independence, re-defining is fine for MVP.
aclient_http_options = {"timeout": 60.0} # 60 seconds timeout for OpenAI calls
if OPENAI_API_KEY:
    gpt_aclient = AsyncOpenAI(api_key=OPENAI_API_KEY, http_client=httpx.AsyncClient(**aclient_http_options))
else:
    gpt_aclient = None # Client remains None if API key is not set

# System prompt to guide the GPT model for medical translation context.
# Security: The prompt itself does not contain user data directly here, but guides the model.
# Avoid constructing prompts by directly concatenating unsanitized user input if possible,
# though for translation, the user's text *is* the primary input.
MEDICAL_SYSTEM_PROMPT = (
    "You are an expert medical translator. "
    "Translate the provided medical phrase accurately and concisely. "
    "Maintain a professional and empathetic tone suitable for healthcare interactions. "
    "If the input is clearly not a medical phrase, you may indicate that you primarily translate medical content, "
    "but still attempt a general translation if safe and appropriate. "
    "Translate directly without adding conversational fluff unless it's part of the text to translate."
)

async def translate_text(
    text_to_translate: str,
    target_language: str = "isiZulu", # Default target for BUA MVP
    source_language: Optional[str] = "English" # Default source, helps model if known
) -> str:
    """
    Translates text using OpenAI GPT, guided by a medical context prompt.

    Args:
        text_to_translate (str): The text to translate.
        target_language (str): The language to translate into (e.g., "isiZulu", "English").
        source_language (str, optional): The source language of the text. If None, GPT will infer.
                                         Providing it can improve accuracy.
    Returns:
        str: The translated text. Returns an empty string or error message if translation fails
             or if the client is not initialized.
    """
    if not gpt_aclient:
        print("Error: OpenAI client not initialized. Cannot translate text.")
        return "Translation service unavailable: API key missing." # Or empty string

    if not text_to_translate.strip():
        return "" # Nothing to translate

    # Constructing the user prompt for translation
    # Security: `text_to_translate` is user-provided content.
    # While it's meant for translation, be aware that it's passed to an external AI.
    # No direct HTML/script injection risk here as it's processed by GPT, but the content
    # itself is from the user. The risk is more about what the user tries to make the AI say/do,
    # handled by OpenAI's safety systems and careful prompting.
    user_prompt_content = f"Translate the following text from {source_language if source_language else 'the detected language'} to {target_language}: \"{text_to_translate}\""

    try:
        response = await gpt_aclient.chat.completions.create(
            model="gpt-3.5-turbo", # Or "gpt-4" / "gpt-4-turbo" if available and preferred
            messages=[
                {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt_content}
            ],
            temperature=0.3, # Lower temperature for more factual/deterministic translation
            max_tokens=300,  # Adjust based on expected length of typical medical phrases + translations
            # top_p=1.0,
            # frequency_penalty=0.0,
            # presence_penalty=0.0
        )

        translated_text_content = response.choices[0].message.content
        return translated_text_content.strip() if translated_text_content else ""

    except httpx.ReadTimeout:
        print(f"Error calling OpenAI GPT API: ReadTimeout after {aclient_http_options['timeout']} seconds.")
        return "Translation timed out."
    except Exception as e:
        # Security: Log the full error for backend debugging.
        print(f"Error calling OpenAI GPT API: {type(e).__name__} - {e}")
        # Return a generic error message or an empty string.
        return "Translation failed." # Or empty string ""
