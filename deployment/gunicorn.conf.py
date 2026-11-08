"""
Gunicorn configuration for EASYTECH THATTA production.

Formula:
    workers = (2 × CPU cores) + 1
    threads = 2-4 for I/O-bound Django

Adjust based on server size:
    2 GB RAM  -> 3 workers, 4 threads
    4 GB RAM  -> 5 workers, 4 threads
    8 GB RAM  -> 9 workers, 4 threads
"""
import multiprocessing

# ---------- Binding ----------
bind = 'unix:/run/gunicorn/easystech.sock'
# Alternative (direct TCP, no Nginx):
# bind = '127.0.0.1:8001'

# ---------- Workers ----------
workers = min(multiprocessing.cpu_count() * 2 + 1, 9)
worker_class = 'sync'
threads = 4
worker_connections = 1000
max_requests = 1000               # Recycle workers (memory leak protection)
max_requests_jitter = 100

# ---------- Timeouts ----------
timeout = 60
graceful_timeout = 30
keepalive = 5

# ---------- Logging ----------
accesslog = '/var/www/easystech/logs/gunicorn_access.log'
errorlog = '/var/www/easystech/logs/gunicorn_error.log'
loglevel = 'info'
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# ---------- Process naming ----------
proc_name = 'easystech'

# ---------- Security ----------
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# ---------- Server hooks ----------
def on_starting(server):
    server.log.info("Starting EASYTECH THATTA...")

def when_ready(server):
    server.log.info(f"Server ready. Workers: {workers}, Threads: {threads}")

def worker_int(worker):
    worker.log.info(f"Worker {worker.pid} received interrupt")

def on_exit(server):
    server.log.info("Shutting down EASYTECH THATTA...")