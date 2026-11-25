import tkinter
from collections.abc import Iterator
from itertools import islice
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

from url import URL

HSTEP, VSTEP = 13, 18
SCROLL_STEP = 20

EMOJI_DIR = Path(__file__).parent / "openmojis"
EMOJI_SIZE = 16

HTML_ENTITIES: dict[str, str] = {
    "&lt;": "<",
    "&gt;": ">",
    "&amp;": "&",
    "nbsp;": " ",
    "quot;": '"',
}


class Browser:
    def __init__(self) -> None:
        self._emoji_images: dict[str, ImageTk.PhotoImage | None] = {}
        self._dir_text: str | None = None

        self.window = tkinter.Tk()
        self.width = self.window.winfo_screenwidth()
        self.height = self.window.winfo_screenheight()

        self.window.geometry(f"{self.width}x{self.height}+0+0")

        self.scrollbar = ttk.Scrollbar(
            self.window, orient="vertical", command=self._on_scrollbar
        )
        self.scrollbar.pack(side="right", fill="y")

        self.canvas = tkinter.Canvas(self.window, width=self.width, height=self.height)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scroll = 0
        self._text = ""
        self._display_list: list[tuple[int, int, str]] = []

        self.window.bind("<Down>", self._scroll_down)
        self.window.bind("<Up>", self._scroll_up)
        self.window.bind("<MouseWheel>", self._scroll_mouse)
        self.window.bind("<Button-4>", self._scroll_up)
        self.window.bind("<Button-5>", self._scroll_down)

        self.canvas.bind("<Configure>", self._on_resize)

        self.window.focus_force()

    def load(self, url: URL, dir_text: str | None) -> None:
        body = url.request()
        raw_text = body if "view-source" in url.scheme else self._lex(body)
        self._text = raw_text
        self._dir_text = dir_text

        self._display_list = list(self._layout(self._text))
        self._clamp_scroll()
        self._draw()

        self.window.mainloop()

    def _max_scroll(self) -> int:
        return max(0, self._content_height() - self.height)

    def _on_scrollbar(self, *args: str) -> None:
        total = self._content_height()
        if total <= self.height:
            return

        if args[0] == "moveto":
            fraction = float(args[1])
            self.scroll = int(fraction * total)
        elif args[0] == "scroll":
            amount = int(args[1])
            unit = args[2]
            step = SCROLL_STEP if unit == "units" else self.height
            self.scroll += amount * step

        self._clamp_scroll()
        self._draw()

    def _content_height(self) -> int:
        if not self._display_list:
            return 0

        max_y = max(y for _, y, _ in self._display_list)

        return max_y + VSTEP

    def _clamp_scroll(self) -> None:
        self.scroll = max(0, min(self._max_scroll(), self.scroll))

    def _on_resize(self, event: tkinter.Event) -> None:
        if event.width == self.width and event.height == self.height:
            return

        self.width = event.width
        self.height = event.height

        if self._text:
            self._display_list = list(self._layout(self._text))
            self._clamp_scroll()
            self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")

        for x, y, c in self._display_list:
            if y - self.scroll < 0 or y - self.scroll > self.height:
                continue

            if self._is_emoji(c):
                photo = self._get_emoji_image(c)
                if photo is not None:
                    self.canvas.create_image(
                        x, y - self.scroll, image=photo, anchor="nw"
                    )
                    continue

            self.canvas.create_text(x, y - self.scroll, text=c, anchor="nw")

        self._update_scrollbar()

    def _update_scrollbar(self) -> None:
        total = self._content_height()

        if total <= self.height:
            self.scrollbar.pack_forget()
            return

        if not self.scrollbar.winfo_ismapped():
            self.scrollbar.pack(side="right", fill="y", before=self.canvas)

        first = self.scroll / total

        last = min(1.0, (self.scroll + self.height) / total)

        self.scrollbar.set(first, last)

    def _char_advance(self, char: str) -> int:
        if self._is_emoji(char) and self._get_emoji_image(char) is not None:
            return max(HSTEP, EMOJI_SIZE)
        return HSTEP

    def _layout(self, body: str) -> Iterator[tuple[int, int, str]]:
        if self._dir_text == "vertical":
            yield from self._layout_vertical(body)
            return

        lines: list[tuple[list[str], int]] = []
        current_chars: list[str] = []
        current_width = 0
        max_line_width = max(HSTEP, self.width - 2 * HSTEP)

        for c in body:
            if c == "\r":
                continue
            if c == "\n":
                lines.append((current_chars, current_width))
                current_chars = []
                current_width = 0
                continue

            step = self._char_advance(c)
            if current_chars and current_width + step > max_line_width:
                lines.append((current_chars, current_width))
                current_chars = [c]
                current_width = step
            else:
                current_chars.append(c)
                current_width += step

        if current_chars or not lines:
            lines.append((current_chars, current_width))

        cursor_y = VSTEP
        is_rtl = self._dir_text == "rtl"

        for chars, line_width in lines:
            if not chars:
                cursor_y += VSTEP * 2
                continue

            if is_rtl:
                cursor_x = max(HSTEP, self.width - HSTEP - line_width)
            else:
                cursor_x = HSTEP

            for c in chars:
                yield (cursor_x, cursor_y, c)
                cursor_x += self._char_advance(c)

            cursor_y += VSTEP

    def _layout_vertical(self, body: str) -> Iterator[tuple[int, int, str]]:
        col_step = max(HSTEP, EMOJI_SIZE)
        cursor_x = self.width - HSTEP - col_step
        cursor_y = VSTEP

        for c in body:
            if c == "\r":
                continue
            if c == "\n":
                cursor_y = VSTEP
                cursor_x -= col_step * 2
                if cursor_x < HSTEP:
                    cursor_x = self.width - HSTEP - col_step
                continue

            step = self._char_advance(c)
            yield (cursor_x, cursor_y, c)
            cursor_y += step

            if cursor_y >= self.height - VSTEP:
                cursor_y = VSTEP
                cursor_x -= col_step
                if cursor_x < HSTEP:
                    cursor_x = self.width - HSTEP - col_step

    def _lex(self, body: str) -> str:
        return "".join(self._get_chars(body))

    def _get_chars(self, body: str) -> Iterator[str]:
        in_tag = False
        chars = enumerate(body)
        for i, c in chars:
            match c:
                case "<":
                    in_tag = True
                case ">":
                    in_tag = False
                case _ if not in_tag:
                    yield self._get_text(chars, body, c, i)

    def _get_text(self, chars, body: str, c: str, i: int) -> str:
        val = HTML_ENTITIES.get(body[i : i + 4])
        if val is None:
            return c
        next(islice(chars, 3, 3), None)
        return val

    def _scroll_down(self, event: tkinter.Event) -> None:
        self.scroll = min(self._max_scroll(), self.scroll + SCROLL_STEP)
        self._draw()

    def _scroll_up(self, event: tkinter.Event) -> None:
        self.scroll = max(0, self.scroll - SCROLL_STEP)
        self._draw()

    def _scroll_mouse(self, event: tkinter.Event) -> None:
        steps = event.delta // 120
        self.scroll = max(0, min(self._max_scroll(), self.scroll - steps * SCROLL_STEP))
        self._draw()

    def _get_emoji_image(self, char: str) -> ImageTk.PhotoImage | None:
        if char in self._emoji_images:
            return self._emoji_images[char]

        filename = f"{ord(char):X}.png"
        path = EMOJI_DIR / filename
        if not path.exists():
            self._emoji_images[char] = None
            return None

        img = (
            Image.open(path)
            .convert("RGBA")
            .resize((EMOJI_SIZE, EMOJI_SIZE), Image.Resampling.LANCZOS)
        )
        photo = ImageTk.PhotoImage(img)
        self._emoji_images[char] = photo
        return photo

    def _is_emoji(self, char: str) -> bool:
        code = ord(char)
        return 0x1F300 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF
