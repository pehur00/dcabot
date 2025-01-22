# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the Python scripts and requirements file into the container
COPY MartingaleTradingStrategy.py PhemexClient.py TradingClient.py requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the entry point to your Python script
ENTRYPOINT ["python", "MartingaleTradingStrategy.py"]
