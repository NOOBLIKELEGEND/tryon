"""RQ worker entrypoint.

Run with: python worker.py

Or in Docker: `CMD ["python","worker.py"]`
"""
from redis import Redis
from rq import Worker, Queue, Connection
import os

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(redis_url)

if __name__ == "__main__":
    with Connection(redis_conn):
        qs = ["tryon"]
        worker = Worker(map(Queue, qs))
        worker.work()
