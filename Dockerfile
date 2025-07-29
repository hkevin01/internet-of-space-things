FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY docs/ ./docs/
COPY README.md .

# Create logs directory
RUN mkdir -p /app/logs

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port for web interface
EXPOSE 8000

# Run the application
CMD ["python", "src/main.py"]
