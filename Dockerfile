# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the Python scripts and requirements file into the container
# Copy the Python scripts, directories, and requirements file into the container
COPY main.py requirements.txt /app/
COPY clients /app/clients/
COPY strategies /app/strategies/
COPY workflows /app/workflows/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the entry point to your Python script
ENTRYPOINT ["python", "main.py"]
