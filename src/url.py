import gzip
import re

from cache import Cache
from socket_cache import SocketCache

HEADERS = {
    "Connection": "keep-alive",
    "Accept-Encoding": "gzip",
    "User-Agent": "RefAragao/1.0",
}

LOCATION_REGEX = re.compile(
    r"^(?:"
    r"(?P<scheme>https?)://(?P<host>[a-zA-Z0-9.-]+)(?::(?P<port>\d{1,5}))?(?P<abs_path>/[^\s]*)?"
    r")$"
)

REDIRECT_STATUSES = {"301", "302", "303", "307", "308"}

CACHE_STATUS = {"200", "203", "204", "206", "300", "301", "404", "410"}


class URL:
    def __init__(self, url: str):

        self.cache = Cache()

        self._decompose_url(url)

    def request(self) -> str:
        match self.scheme:
            case "http" | "https":
                return self.request_http()
            case "file":
                return self.request_file()
            case "data":
                return self.request_data()
            case "view-source":
                return URL(self.path).request()
            case "about:blank":
                return ""

        return ""

    def request_http(self) -> str:
        result_cache = self.cache.get(self.url)

        if result_cache is not None:
            print(f"Cache hit for {self.url}")
            return result_cache

        s = SocketCache().connect(self.scheme, self.host, self.port)

        request = f"GET {self.path} HTTP/1.1\r\n"
        request += f"Host: {self.host}\r\n"
        for header, value in HEADERS.items():
            request += f"{header}: {value}\r\n"
        request += "\r\n"

        response = s.send(request.encode("utf-8"))

        status_line = response.readline().decode("utf-8")
        version, status, explanation = status_line.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline()
            if not line or line in (b"\r\n", b"\n"):
                break

            decode_line = line.decode("utf-8", errors="replace")
            if ":" not in decode_line:
                continue

            header, value = decode_line.split(":", 1)
            response_headers[header.strip().casefold()] = value.strip()

        if self._is_redirection(status, response_headers):
            return self._redirect(response_headers, 1)

        raw_content = b""

        if response_headers.get("transfer-encoding") == "chunked":
            chunks = []
            while True:
                line = response.readline().strip()
                if not line:
                    continue
                chunk_size = int(line.split(b";")[0], 16)
                if chunk_size == 0:
                    response.readline()
                    break
                chunks.append(response.read(chunk_size))
                response.readline()
            raw_content = b"".join(chunks)
        elif "content-length" in response_headers:
            content_length = int(response_headers["content-length"])
            raw_content = response.read(content_length)
        else:
            raw_content = response.read()

        if response_headers.get("content-encoding") == "gzip":
            raw_content = gzip.decompress(raw_content)

        content = raw_content.decode("utf-8")

        if status in CACHE_STATUS:
            cache_control = response_headers.get("cache-control", None)

            match cache_control:
                case None:
                    self.cache.set(self.url, content)
                case _ if "max-age" in cache_control:
                    max_age = int(
                        response_headers.get("cache-control", "0").split("=")[-1]
                    )
                    self.cache.set(self.url, content, max_age)
                case _:
                    pass

        return content

    def _is_redirection(self, status: str, response_headers: dict[str, str]) -> bool:
        if status not in REDIRECT_STATUSES:
            return False

        return response_headers.get("location") is not None

    def _redirect(self, response_headers, redirect_count: int) -> str:

        if redirect_count > 5:
            raise TooManyRedirects("Too many redirects")

        location = response_headers.get("location")

        url = (
            location
            if self._is_url_valid(location)
            else f"{self.scheme}://{self.host}{location}"
        )

        print(f"Redirecting to {url}...")

        self._decompose_url(url)

        return self.request_http()

    def _decompose_url(self, url: str):
        if self._is_url_valid(url) is False:
            self.scheme = "about:blank"
            self.url = "about:blank"
        else:
            self.scheme, url = url.split(":", 1)
            assert self.scheme in ("http", "https", "file", "data", "view-source"), (
                "Invalid scheme"
            )

            if "http" not in self.scheme:
                self.path = url
                return

            url = url.lstrip("/")

            if "/" not in url:
                url = url + "/"

            self.host, url = url.split("/", 1)
            self.path = "/" + url

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)
            else:
                self.port = 443 if self.scheme == "https" else 80

            self.url = f"{self.scheme}://{self.host}:{self.port}{self.path}"

    def _is_url_valid(self, url: str) -> bool:
        match LOCATION_REGEX.match(url):
            case None:
                return False
            case _:
                return True

    def request_file(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    def request_data(self):
        _, data = self.path.split(",", 1)
        return data


class TooManyRedirects(Exception):
    pass
