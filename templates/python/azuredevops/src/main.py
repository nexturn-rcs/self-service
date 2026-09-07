from fastapi import FastAPI
from prometheus_client import Counter, generate_latest
from fastapi.responses import PlainTextResponse
import os

app = FastAPI(
    title="Python Service",
    version="1.0.0"
)

# Prometheus metric
request_counter = Counter(
    "http_requests_total",
    "Total HTTP requests"
)


@app.get("/")
def root():
    request_counter.inc()
    return {
        "message": "Python Service is running"
    }


@app.get("/health")
def health():
    request_counter.inc()
    return {
        "status": "UP"
    }


@app.get("/ready")
def ready():
    request_counter.inc()

    # Add dependency checks here later
    # Database
    # Redis
    # External APIs

    return {
        "status": "READY"
    }


@app.get("/info")
def info():
    request_counter.inc()

    return {
        "service": "python-service",
        "version": "1.0.0",
        "environment": os.getenv("APP_ENV", "unknown")
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest().decode("utf-8")
