# Kuulis load test runner (doc 18): k6 + a small control API + a fake Expo push endpoint.
# Coolify: base directory /loadtest, Dockerfile build pack, port 8080, persistent volume on /data.
FROM grafana/k6:1.3.0 AS k6

FROM python:3.12-slim
COPY --from=k6 /usr/bin/k6 /usr/bin/k6
WORKDIR /app
COPY runner/requirements.txt runner/requirements.txt
RUN pip install --no-cache-dir -r runner/requirements.txt
COPY . .
ENV DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["sh", "/app/runner/entrypoint.sh"]
