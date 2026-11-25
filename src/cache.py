import re
import time

CACHE: dict[str, tuple[str, float]] = {}


class Cache:
    def __init__(self) -> None:
        pass

    def get(self, url: str) -> str | None:
        result_cache = CACHE.get(url)

        if result_cache is None:
            return None

        content, timeout = result_cache

        print(264)

        if content is None:
            return None

        if timeout < time.time():
            CACHE.pop(url, None)
            return None

        return content

    def set(self, url: str, content: str, max_age: int = 300):
        print(f"Cache set for {url} with max-age {max_age}")
        timeout = max_age + time.time()
        CACHE[url] = (content, timeout)

    def clear(self, url: str):
        CACHE.pop(url, None)
