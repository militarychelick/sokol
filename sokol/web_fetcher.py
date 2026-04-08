# -*- coding: utf-8 -*-
"""
SOKOL v7 — Web Fetcher
Extract clean text from web pages via urllib (no browser needed).
Allows the agent to 'read' and summarize web content.
"""
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from .core import INTERRUPT
class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract readable text."""
    SKIP_TAGS = {
        "script", "style", "noscript", "head", "meta", "link",
        "svg", "path", "iframe", "object", "embed",
    }
    def __init__(self):
        super().__init__()
        self._text_parts = []
        self._skip_depth = 0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag.lower() in ("br", "hr"):
            self._text_parts.append("\n")
        elif tag.lower() in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                              "li", "tr", "blockquote", "article", "section"):
            self._text_parts.append("\n")
    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag.lower() in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                              "li", "tr", "blockquote"):
            self._text_parts.append("\n")
    def handle_data(self, data):
        if self._skip_depth == 0:
            self._text_parts.append(data)
    def get_text(self):
        raw = "".join(self._text_parts)
        # collapse whitespace
        lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
        return "\n".join(lines)
class WebFetcher:
    """
    Fetch and extract clean text from web pages.
    Uses urllib + HTMLParser — no external dependencies.
    """
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    @classmethod
    def fetch_text(cls, url, max_chars=5000, timeout=15):
        """
        Fetch URL and return clean text content.
        Args:
            url: Web page URL
            max_chars: Maximum characters to return
            timeout: Request timeout in seconds
        Returns:
            (success: bool, text: str)
        """
        INTERRUPT.check()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": cls.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,*/*",
                    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
                },
            )
            INTERRUPT.check()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                # Determine encoding
                encoding = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].split(";")[0].strip()
                    encoding = charset
                raw_bytes = resp.read(500_000)  # max 500KB
                try:
                    html = raw_bytes.decode(encoding, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    html = raw_bytes.decode("utf-8", errors="replace")
            # Extract text
            extractor = _HTMLTextExtractor()
            extractor.feed(html)
            text = extractor.get_text()
            # Extract title
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            if not text.strip():
                return False, "Page returned no readable text content."
            # Truncate
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n\n... [truncated, {len(text)} total chars]"
            result = ""
            if title:
                result += f"Title: {title}\nURL: {url}\n{'─' * 40}\n\n"
            result += text
            return True, result
        except urllib.error.HTTPError as e:
            return False, f"HTTP Error {e.code}: {e.reason} for {url}"
        except urllib.error.URLError as e:
            return False, f"URL Error: {e.reason} for {url}"
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"Fetch error: {e}"
    @classmethod
    def fetch_links(cls, url, timeout=15):
        """Fetch all links from a page."""
        INTERRUPT.check()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read(500_000).decode("utf-8", errors="replace")
            links = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
            # Filter and deduplicate
            seen = set()
            result = []
            for link in links:
                if link.startswith(("#", "javascript:", "mailto:")):
                    continue
                if link not in seen:
                    seen.add(link)
                    result.append(link)
            return True, result
        except Exception as e:
            return False, f"Link fetch error: {e}"
    @classmethod
    def summarize_url(cls, url, max_chars=3000):
        """Fetch page and prepare for LLM summarization."""
        ok, text = cls.fetch_text(url, max_chars=max_chars)
        if not ok:
            return ok, text
        return True, text
