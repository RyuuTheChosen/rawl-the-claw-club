from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# Match metrics
matches_total = Counter("rawl_matches_total", "Total matches run", ["game_id", "status"])
matches_active = Gauge("rawl_matches_active", "Currently active matches")
match_duration_seconds = Histogram(
    "rawl_match_duration_seconds", "Match duration in seconds", ["game_id"],
    buckets=[30, 60, 120, 180, 300, 600],
)

# Inference metrics
inference_latency_seconds = Histogram(
    "rawl_inference_latency_seconds", "Model inference latency",
    buckets=[0.001, 0.002, 0.005, 0.01, 0.02, 0.05],
)

# WebSocket metrics
ws_connections = Gauge("rawl_ws_connections", "Active WebSocket connections", ["channel"])

# API metrics
api_requests_total = Counter("rawl_api_requests_total", "API requests", ["method", "endpoint", "status"])
api_request_duration_seconds = Histogram(
    "rawl_api_request_duration_seconds", "API request duration",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

# Training metrics
training_jobs_total = Counter("rawl_training_jobs_total", "Training jobs", ["status"])
training_jobs_active = Gauge("rawl_training_jobs_active", "Active training jobs")

# S3 metrics
s3_uploads_total = Counter("rawl_s3_uploads_total", "S3 upload attempts", ["status"])

# Solana metrics
solana_tx_total = Counter("rawl_solana_tx_total", "Solana transactions", ["instruction", "status"])
