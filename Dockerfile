# syntax=docker/dockerfile:1
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
COPY frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.node.json frontend/tailwind.config.js frontend/postcss.config.js ./
COPY frontend/index.html ./
COPY frontend/src ./src
RUN npm install && npm run build

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY frontend/dist ./frontend/dist
EXPOSE 8000
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
