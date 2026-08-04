FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8765

WORKDIR /app

COPY app.py requirements.txt ./
COPY relationship_archaeology ./relationship_archaeology
COPY static ./static
COPY sample_data ./sample_data

EXPOSE 8765

CMD ["python", "app.py"]
