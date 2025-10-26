workers = 4
bind = "0.0.0.0:8000"
timeout = 120  # Increased timeout for long-running try-on operations
max_requests = 1000
max_requests_jitter = 50