"""Gunicorn production server configuration."""

import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = "info"
