# backend/Dockerfile

FROM python:3.12.2-slim

# Create working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI code into the container
COPY . /app

# Expose port 8000 within Docker
EXPOSE 8000

# By default, run uvicorn on 0.0.0.0:8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
