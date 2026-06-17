import os
from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT = os.environ.get("API_RATE_LIMIT", "10/minute")
limiter = Limiter(key_func=get_remote_address)
