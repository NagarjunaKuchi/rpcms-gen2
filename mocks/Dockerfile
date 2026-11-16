# RPCMS external-systems mocks (dev only). Stdlib Python, no dependencies.
FROM python:3.12-alpine
WORKDIR /app
COPY server.py /app/server.py
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python3", "/app/server.py"]
