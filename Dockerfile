# Use Python 3.11 slim image with UV pre-installed
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Set the working directory 
WORKDIR /gen-agent

# Install curl for the health check
RUN apt-get update --allow-releaseinfo-change && \
    apt-get install -y --no-install-recommends --allow-unauthenticated ca-certificates debian-archive-keyring && \
    apt-get update --allow-releaseinfo-change && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set UV to use the system Python and copy mode for linking
ENV UV_SYSTEM_PYTHON=1
ENV UV_LINK_MODE=copy

# Copy the requirements.txt file and install Python dependencies
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# Install system dependencies for pdf2image (poppler-utils)
RUN set -eux; \
    apt-get update || true; \
    apt-get install -y --no-install-recommends gnupg ca-certificates || true; \
    apt-get install -y --allow-unauthenticated poppler-utils || true; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies for PDF/image processing
RUN uv pip install --system pdf2image pillow

# Copy your main application code and additional files
COPY app.py ./
COPY rag_utils.py ./
COPY markdown_to_docx.py ./
COPY models.py ./
COPY search_utils.py ./
COPY document_utils.py ./
COPY prompts.py ./

# If there are other files or directories to include, add them here
# COPY other_file.py ./
# COPY your_directory/ ./your_directory/
COPY .streamlit/ ./.streamlit/
COPY .env ./

# Expose port 8501 for Streamlit
EXPOSE 8501

# Define a health check for the container using curl
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Set the entrypoint to run the Streamlit application
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
