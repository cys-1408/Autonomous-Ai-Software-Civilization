FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Expose ports
EXPOSE 8000 8765 9091

# Run the Command Center
CMD ["python", "-m", "uvicorn", "backend.web.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
