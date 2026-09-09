# Use a modern base image
FROM python:3.11-slim-bookworm

# Install prerequisites
RUN apt-get update -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false && \
    apt-get install -y curl gnupg apt-transport-https unixodbc-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render will override with $PORT)
EXPOSE 10000

# Start with Gunicorn, binding to Render's dynamic $PORT
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "--workers", "4"]
