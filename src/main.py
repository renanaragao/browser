from browser import Browser
from url import URL


def load(url: URL, dir_text: str | None = None) -> None:
    Browser().load(url, dir_text)


if __name__ == "__main__":
    import sys

    dir_text = None

    if len(sys.argv) > 1:
        url = sys.argv[1]
        arg = next((x for x in sys.argv[2:] if x.startswith("--dir-text=")), None)
        dir_text = arg.split("=")[1] if arg is not None else None
    else:
        url = "file:///home/refaragao/Downloads/test.html"

    load(URL(url), dir_text)
