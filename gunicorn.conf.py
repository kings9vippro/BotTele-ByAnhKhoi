# Author: Dev Anh Khôi · Version: 1.2.0.
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 1
threads = 16
worker_class = "gthread"
timeout = 120
keepalive = 35
accesslog = "-"
# Log the URL path only, never the OAuth authorization code/query string.
access_log_format = '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
errorlog = "-"
preload_app = False
