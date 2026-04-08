# -*- coding: utf-8 -*-
"""
Groq (OpenAI-compatible) as primary LLM when GROQ_API_KEY is set; Ollama fallback.
Vision steps always use the embedded OllamaClient.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Generator, Iterator

from .config import (
    FAST_MAX_TOKENS,
    FAST_TEMPERATURE,
    FULL_MAX_TOKENS,
    FULL_TEMPERATURE,
    OLLAMA_API_BASE,
    OLLAMA_MODEL,
)
from .core import INTERRUPT, OllamaClient

_log = logging.getLogger("sokol.llm_hybrid")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_gpu_hint_logged = False


def _maybe_log_gpu_hint(use_groq: bool) -> None:
    global _gpu_hint_logged
    if use_groq or _gpu_hint_logged:
        return
    _gpu_hint_logged = True
    _log.info(
        "Using local Ollama only. If responses are slow, check: "
        "`ollama ps` (GPU offload), install CUDA/ROCm Ollama build, OLLAMA_NUM_GPU in config."
    )


def _groq_key() -> str:
    return (os.environ.get("GROQ_API_KEY") or "").strip()


def _groq_model() -> str:
    return (os.environ.get("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()


class HybridLLMClient:
    """
    Delegates chat/classify to Groq when key present; falls back to Ollama on failure.
    Shares conversation history with inner OllamaClient for consistency on fallback.
    """

    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        api_base: str = OLLAMA_API_BASE,
        system_message: str = "",
        classify_prompt: str = "",
    ):
        self._ollama = OllamaClient(
            model=model,
            api_base=api_base,
            system_message=system_message,
            classify_prompt=classify_prompt,
        )
        self._groq_key = _groq_key()
        self._groq_model = _groq_model()
        self.system_message = system_message
        self.classify_prompt = classify_prompt
        _maybe_log_gpu_hint(bool(self._groq_key))

    @property
    def history(self):
        return self._ollama.history

    @property
    def model(self):
        return self._groq_model if self._groq_key else self._ollama.model

    def reset(self) -> None:
        self._ollama.reset()

    def warmup(self) -> None:
        self._ollama.warmup()

    def abort(self) -> None:
        self._ollama.abort()

    def vision_step(self, goal: str, screen_elements: str, previous_actions: str) -> str:
        return self._ollama.vision_step(goal, screen_elements, previous_actions)

    def _groq_request(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        stream: bool,
        timeout: int = 90,
    ):
        payload = {
            "model": self._groq_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            GROQ_API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._groq_key}",
            },
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=timeout)

    def _groq_chat_complete(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        timeout: int = 90,
    ) -> str:
        resp = self._groq_request(
            messages, max_tokens=max_tokens, temperature=temperature, stream=False, timeout=timeout
        )
        try:
            body = json.loads(resp.read().decode("utf-8"))
        finally:
            resp.close()
        choices = body.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return (msg.get("content") or "").strip()

    def _groq_chat_stream(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        timeout: int = 90,
    ) -> Generator[str, None, None]:
        resp = self._groq_request(
            messages, max_tokens=max_tokens, temperature=temperature, stream=True, timeout=timeout
        )
        try:
            while True:
                raw = resp.readline()
                if not raw:
                    break
                line = raw.strip()
                if not line or line == b"data: [DONE]":
                    continue
                if not line.startswith(b"data: "):
                    continue
                try:
                    obj = json.loads(line[6:].decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                for ch in obj.get("choices") or []:
                    delta = ch.get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        yield piece
        finally:
            resp.close()

    def classify(self, user_message: str, max_user_chars: int = 1000) -> str:
        if not self._groq_key:
            return self._ollama.classify(user_message, max_user_chars=max_user_chars)
        um = (user_message or "")[:max_user_chars]
        messages = [
            {"role": "system", "content": self.classify_prompt},
            {"role": "user", "content": um},
        ]
        try:
            INTERRUPT.check()
            out = self._groq_chat_complete(
                messages,
                max_tokens=min(FAST_MAX_TOKENS, 256),
                temperature=FAST_TEMPERATURE,
                timeout=45,
            )
            if out:
                return out
        except Exception as e:
            _log.warning("Groq classify failed, falling back to Ollama: %s", e)
        return self._ollama.classify(user_message, max_user_chars=max_user_chars)

    def chat(self, user_message: str, one_shot: bool = False) -> str:
        if not self._groq_key:
            return self._ollama.chat(user_message, one_shot=one_shot)
        messages = [{"role": "system", "content": self.system_message}]
        pushed = False
        if not one_shot:
            self._ollama.history.append({"role": "user", "content": user_message})
            pushed = True
            messages.extend(self._ollama.history[-self._ollama._max_history :])
        else:
            messages.append({"role": "user", "content": user_message})
        try:
            INTERRUPT.check()
            text = self._groq_chat_complete(
                messages,
                max_tokens=FULL_MAX_TOKENS,
                temperature=FULL_TEMPERATURE,
                timeout=90,
            )
            if text:
                if not one_shot:
                    self._ollama.history.append({"role": "assistant", "content": text})
                return text
            if pushed:
                self._ollama.history.pop()
            return self._ollama.chat(user_message, one_shot=one_shot)
        except Exception as e:
            _log.warning("Groq chat failed, falling back to Ollama: %s", e)
        if pushed:
            self._ollama.history.pop()
        return self._ollama.chat(user_message, one_shot=one_shot)

    def chat_stream(self, user_message: str, one_shot: bool = False) -> Iterator[str]:
        if not self._groq_key:
            yield from self._ollama.chat_stream(user_message, one_shot=one_shot)
            return
        messages = [{"role": "system", "content": self.system_message}]
        pushed = False
        if not one_shot:
            self._ollama.history.append({"role": "user", "content": user_message})
            pushed = True
            messages.extend(self._ollama.history[-self._ollama._max_history :])
        else:
            messages.append({"role": "user", "content": user_message})
        full: list[str] = []
        try:
            INTERRUPT.check()
            for token in self._groq_chat_stream(
                messages,
                max_tokens=FULL_MAX_TOKENS,
                temperature=FULL_TEMPERATURE,
                timeout=90,
            ):
                INTERRUPT.check()
                full.append(token)
                yield token
            if not one_shot and full:
                self._ollama.history.append({"role": "assistant", "content": "".join(full)})
            return
        except Exception as e:
            _log.warning("Groq chat_stream failed, falling back to Ollama: %s", e)
        if pushed:
            self._ollama.history.pop()
        yield from self._ollama.chat_stream(user_message, one_shot=one_shot)
