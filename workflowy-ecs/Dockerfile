FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the 'workflowy' directory (main code)
COPY workflowy/ ./workflowy/

# Copy the ECS entry point
COPY ecs-workflowy-wrapper.py .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the processor
CMD ["python", "ecs-workflowy-wrapper.py"]
