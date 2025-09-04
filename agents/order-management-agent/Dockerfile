FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash supervisor
RUN chown -R supervisor:supervisor /app

# Switch to non-root user
USER supervisor

# Set environment variables
ENV PYTHONPATH=/app
ENV AGENT_PORT=8001

# Expose port
EXPOSE 8001

# Set working directory to src
WORKDIR /app/src

# Start the agent
CMD ["python", "main.py"]
