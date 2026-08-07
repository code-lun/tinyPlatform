FROM python:3.11-alpine

WORKDIR /app

RUN apk add --no-cache bash

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV BACKEND_API_URL=http://backend:8000
ENV REQUEST_TIMEOUT=30

CMD ["python", "server.py"]