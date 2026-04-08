# -*- coding: utf-8 -*-
"""
SOKOL v7.9 — Deep Research Agent
Searches multiple resources, extracts facts, and structures data.
Optimized for streaming output.
"""
import re
import time
import urllib.request
import urllib.parse
from .web_fetcher import WebFetcher
from .core import INTERRUPT

class DeepResearchAgent:
    """
    Collects information from multiple web sources and structures it.
    """
    
    @classmethod
    def search_links(cls, query, count=3):
        """
        Get search result links using DuckDuckGo (no API key needed).
        """
        INTERRUPT.check()
        encoded_query = urllib.parse.quote(query)
        # Using DDG HTML version for easier scraping
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            
            # Extract result links
            # DDG HTML results are usually in <a class="result__a" href="...">
            links = []
            # Simplified regex to find links that look like external URLs
            # href="/l/?kh=-1&amp;uddg=https%3A%2F%2Fru.wikipedia.org%2Fwiki%2F..."
            matches = re.findall(r'uddg=([^&"\']+)', html)
            for m in matches:
                link = urllib.parse.unquote(m)
                if link.startswith("http") and "duckduckgo.com" not in link:
                    if link not in links:
                        links.append(link)
                if len(links) >= count:
                    break
            
            # Fallback if regex failed
            if not links:
                links = re.findall(r'href="(https?://[^"]+)"', html)
                links = [l for l in links if "duckduckgo.com" not in l][:count]
                
            return links
        except Exception:
            return []

    @classmethod
    def research(cls, topic, gui):
        """
        Perform deep research and stream results to GUI.
        """
        gui.ui_call(lambda: gui._status(f"Searching for: {topic}..."))
        links = cls.search_links(topic, count=3)
        
        if not links:
            yield "Не удалось найти подходящие ресурсы для исследования."
            return

        yield f"🔍 Найдено ресурсов: {len(links)}. Начинаю сбор данных...\n"
        
        all_content = []
        for i, link in enumerate(links, 1):
            INTERRUPT.check()
            domain = urllib.parse.urlparse(link).netloc
            gui.ui_call(lambda: gui._status(f"Fetching {i}/{len(links)}: {domain}..."))
            
            ok, text = WebFetcher.fetch_text(link, max_chars=4000)
            if ok:
                all_content.append(f"--- SOURCE {i}: {link} ---\n{text}\n")
                yield f"✅ Обработан ресурс {i}: {domain}\n"
            else:
                yield f"⚠️ Пропущен ресурс {i}: {domain} (ошибка загрузки)\n"

        if not all_content:
            yield "❌ Не удалось получить текст ни из одного источника."
            return

        yield "\n🧠 Анализирую и структурирую информацию...\n\n"
        
        # Now use LLM to summarize and structure
        combined_text = "\n".join(all_content)
        prompt = (
            f"Ты — агент глубокого исследования СОКОЛ. Тема: '{topic}'.\n"
            f"Ниже приведены выжимки из нескольких веб-ресурсов:\n\n"
            f"{combined_text}\n\n"
            "ЗАДАНИЕ:\n"
            "На основе этих данных составь структурированное досье.\n"
            "Обязательно включи разделы:\n"
            "1. Даты (хронология событий)\n"
            "2. Личности (ключевые фигуры)\n"
            "3. Итоги и факты (коротко и по делу)\n\n"
            "Пиши максимально конкретно, без 'воды'. Используй маркированные списки."
        )

        # Stream LLM response
        for token in gui.ollama.chat_stream(prompt, one_shot=True):
            yield token
