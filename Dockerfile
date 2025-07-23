FROM python:3.9-slim

WORKDIR /ResearchAssistant

# Copy requirements file
COPY requirements-core.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements-core.txt

# Copy application code
COPY . .

# Set Python path so imports work correctly
ENV PYTHONPATH="/ResearchAssistant/src"

# Create necessary directories
RUN mkdir -p data/uploads data/cache data/logs

EXPOSE 5000

CMD ["python", "src/main.py"]