"""
SalamaIQ — Configuration Gunicorn (production)
==============================================
Lancement : gunicorn -c gunicorn.conf.py app:app
"""
import multiprocessing
import os

# Adresse d'écoute interne (nginx fait le reverse proxy devant)
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")

# Workers : règle classique (2 x cœurs) + 1, plafonné pour un petit VPS
workers = int(os.getenv("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 5)))
threads = int(os.getenv("GUNICORN_THREADS", 2))

# Robustesse
timeout = 120          # uploads/PDF peuvent être longs
graceful_timeout = 30
keepalive = 5
max_requests = 1000    # recycle les workers pour éviter les fuites mémoire
max_requests_jitter = 100

# Logs vers stdout/stderr (capturés par systemd/journald)
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")

# Identité du process
proc_name = "salamaiq"
