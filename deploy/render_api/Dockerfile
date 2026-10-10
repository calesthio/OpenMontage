# Render API — small FastAPI service that creates render Jobs on demand.
#   docker build -f deploy/render_api/Dockerfile -t <registry>/render-api:latest deploy/render_api
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
