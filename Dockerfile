FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY reach/ ./reach/
RUN mkdir -p /data
ENV HOST=0.0.0.0 PORT=8787 DB_PATH=/data/reach.sqlite3
EXPOSE 8787
CMD ["python", "-m", "reach.server"]
