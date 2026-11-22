import random
import socket
import string
import time
from datetime import datetime

_net_cache = {"ok": True, "ts": 0.0}


def has_internet(timeout: float = 2.0) -> bool:
    """Checks internet reachability with a 10s cache so page navigation is instant."""
    now = time.monotonic()
    if now - _net_cache["ts"] < 10.0:
        return _net_cache["ok"]
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout).close()
        _net_cache["ok"] = True
    except OSError:
        _net_cache["ok"] = False
    _net_cache["ts"] = now
    return _net_cache["ok"]


def generate_trip_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def current_date_str() -> str:
    return datetime.now().strftime("%d %b %Y")


def current_time_str() -> str:
    return datetime.now().strftime("%I:%M %p")