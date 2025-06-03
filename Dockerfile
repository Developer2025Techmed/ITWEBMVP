# Stage 1: Builder stage (Install dependencies)
FROM python:3.10-slim AS builder
WORKDIR /app

ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    PYTHONUNBUFFERED=1

# Copy only the requirements file first to leverage Docker cache for this layer
COPY requirements.txt ./requirements.txt

# Install dependencies
# These will typically go into /usr/local/lib/python3.10/site-packages
# and executables like uvicorn into /usr/local/bin
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final stage (Run the application)
FROM python:3.10-slim
WORKDIR /app

# Set environment variables for Python
ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONUNBUFFERED=1

# Copy installed Python packages from the builder stage to the final stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy executables (like uvicorn) installed by pip from the builder stage to the final stage
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code from the build context to the image.
# This should come AFTER copying dependencies to ensure proper layer caching.
COPY . .

# Expose the port the app runs on (must match Uvicorn command)
EXPOSE 8443

# Recommendation: Add a non-root user to run the application for better security.
# This is commented out for MVP simplicity but highly recommended for production.
# RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
# USER appuser

# Command to run the application.
# Assumes .env variables are passed at runtime and certs are volume-mounted to /app/certs.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8443", "--ssl-keyfile", "/app/certs/privkey.pem", "--ssl-certfile", "/app/certs/fullchain.pem"]
