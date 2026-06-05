FROM python:3.11-slim

WORKDIR /app

# System dependencies for FAISS and scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Create directories for data and models
RUN mkdir -p data models

# Expose API port
EXPOSE 8000

# Default command: build then serve
CMD ["sh", "-c", "python scripts/download_data.py && python scripts/build_index.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
