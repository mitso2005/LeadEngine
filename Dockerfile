FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies and SSL certificates
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Copy requirements file
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Create necessary folders
RUN mkdir -p data exports webhook_endpoint_data apollo_data

# Run the application
CMD ["python", "main.py"]