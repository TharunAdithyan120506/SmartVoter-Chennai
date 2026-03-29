FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if any are needed for mysql-connector
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Exposure
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]
