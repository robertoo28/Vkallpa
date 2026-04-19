from cachetools import TTLCache


def make_ttl_cache(maxsize: int = 256, ttl_seconds: int = 600) -> TTLCache:
    return TTLCache(maxsize=maxsize, ttl=ttl_seconds)
