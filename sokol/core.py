# -*- coding: utf-8 -*-
"""
SOKOL v7.2 — Core Infrastructure (UPGRADED)

KEY CHANGES from v7.1:
  1. STREAMING MODE: reads response token-by-token instead of waiting
  2. TRUE CANCEL: resp.close() sends TCP RST → Ollama STOPS GPU work
     (v7.1 just stopped waiting, but Ollama kept computing for ~48s!)
  3. keep_alive: model stays loaded in VRAM between requests (no reload)
  4. vision_step(): dedicated method for agentic vision-action loop
  5. abort(): force-close any active HTTP stream
  6. warmup(): pre-load model into VRAM on startup
"""
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AdminHelper — UAC elevation and privilege management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from .config import (
    CODE_EXEC_TIMEOUT,
    FAST_CONTEXT_WINDOW,
    FAST_MAX_TOKENS,
    FAST_TEMPERATURE,
    FAST_TOP_K,
    FAST_TOP_P,
    FULL_CONTEXT_WINDOW,
    FULL_MAX_TOKENS,
    FULL_TEMPERATURE,
    FULL_TOP_K,
    FULL_TOP_P,
    NOWINDOW,
    OLLAMA_API_BASE,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_GPU,
    OLLAMA_NUM_THREAD,
    VISION_CONTEXT_WINDOW,
    VISION_MAX_TOKENS,
    VISION_TOP_K,
    VISION_TOP_P,
)


class AdminHelper:
    """
    Helper class for managing administrator privileges.
    Provides UAC elevation and privilege checks.
    """

    # ShellExecuteW: success if return value > 32; errors are <= 32 (WinError.h / shellapi.h)
    _SHELLEXECUTE_ERRORS = {
        0: "Ошибка выполнения (код 0).",
        2: "Файл не найден (SE_ERR_FNF).",
        3: "Путь не найден (SE_ERR_PNF).",
        5: (
            "Доступ запрещён (код 5). Windows часто блокирует повышение прав для python.exe из venv "
            "(Smart App Control / политика, «неизвестный издатель»).\n"
            "  Решение: запустите «python run.py --skip-admin-check» или установите переменную "
            "окружения SOKOL_SKIP_ELEVATION=1; для админ-операций используйте Python с python.org."
        ),
        8: "Недостаточно памяти (SE_ERR_OOM).",
        26: "Общий доступ (SE_ERR_SHARE).",
        27: "Ассоциация не завершена (SE_ERR_ASSOCINCOMPLETE).",
        31: "Нет ассоциации для типа файла (SE_ERR_NOASSOC).",
    }

    @staticmethod
    def explain_shell_execute_error(code: int) -> str:
        if code > 32:
            return ""
        return AdminHelper._SHELLEXECUTE_ERRORS.get(
            code,
            f"Неизвестный код ошибки ShellExecuteW: {code}.",
        )

    @staticmethod
    def is_admin():
        """Check if current process has administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False

    @staticmethod
    def is_windows_store_python():
        """Check if running from Windows Store Python (which can't elevate)."""
        exe = sys.executable.lower()
        return "windowsapps" in exe and "pythonsoftwarefoundation" in exe

    @staticmethod
    def run_as_admin(argv=None, skip_confirm=False):
        """
        Restart current script with admin privileges via UAC prompt.

        Returns:
            False if elevation failed or was cancelled
            True if elevation was triggered (current process should exit)
        """
        if argv is None:
            argv = sys.argv

        # Prevent recursion
        if '--admin-elevated' in argv:
            return True

        # Windows Store Python cannot elevate via ShellExecuteW
        if AdminHelper.is_windows_store_python():
            print("[AdminHelper] Windows Store Python detected - cannot auto-elevate.")
            print("[AdminHelper] Please run as admin manually or install python.org version.")
            # Don't show GUI dialog, just return False to continue without admin
            return False

        if not skip_confirm:
            # Ask user before showing UAC prompt
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            result = messagebox.askyesno(
                "Сокол ИИ — Требуются права администратора",
                "Для полного управления ПК (создание файлов в системных папках, "
                "управление службами, доступ ко всем дискам) Соколу нужны права администратора.\n\n"
                "Запустить от имени администратора?",
                icon='question'
            )
            root.destroy()

            if not result:
                return False

        # Prepare arguments
        args = argv[1:] + ['--admin-elevated']
        args_str = ' '.join(f'"{arg}"' for arg in args)

        try:
            print(f"[AdminHelper] Executing: {sys.executable} {args_str}")
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, args_str, None, 1
            )
            print(f"[AdminHelper] ShellExecuteW returned: {result}")

            if result <= 32:  # Error codes from ShellExecute
                hint = AdminHelper.explain_shell_execute_error(int(result))
                print(f"[AdminHelper] ShellExecute failed with code {result}")
                for line in hint.split("\n"):
                    print(f"[AdminHelper] {line}")
                return False

            # Success - exit current process
            print("[AdminHelper] Elevation successful, exiting...")
            import time
            time.sleep(1)
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Failed to elevate: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def ensure_admin_or_exit(skip_confirm=False):
        """
        Ensure the script is running as admin, otherwise elevate or exit.
        Use this at the very beginning of your application.
        """
        if AdminHelper.is_admin():
            return True

        # Not admin - try to elevate
        if not AdminHelper.run_as_admin(skip_confirm=skip_confirm):
            print("[SOKOL] Запуск без прав администратора. Некоторые функции будут недоступны.")
            print("[SOKOL] Для полного функционала перезапустите с правами администратора.")
            return False

        # If elevation was triggered, we exit; new elevated process takes over
        sys.exit(0)

    @staticmethod
    def ensure_admin_silent():
        """
        Silently check for admin rights without UAC prompt.
        Returns True if admin, False otherwise.
        Does NOT attempt elevation.
        """
        return AdminHelper.is_admin()

    @staticmethod
    def get_privilege_warning_text(operation=""):
        """Get standardized warning message about missing privileges."""
        op_text = f" для операции '{operation}'" if operation else ""
        return (
            f"⚠️ Недостаточно прав{op_text}.\n"
            "Запустите Сокол от имени администратора:\n"
            "  1. Закройте текущее окно Сокола\n"
            "  2. Правый клик на ярлыке → 'Запуск от имени администратора'"
        )


class SystemHelper:
    """Various system-level helper functions."""

    @staticmethod
    def get_windows_version():
        """Get Windows version info."""
        try:
            result = subprocess.run(
                ['wmic', 'os', 'get', 'Caption,Version', '/value'],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split('\n')
            info = {}
            for line in lines:
                if '=' in line:
                    k, v = line.split('=', 1)
                    info[k.strip()] = v.strip()
            return info
        except Exception:
            return {}

    @staticmethod
    def get_user_friendly_path(path):
        """Convert path to user-friendly form with environment variables."""
        home = str(Path.home())
        if path.startswith(home):
            return path.replace(home, '%USERPROFILE%', 1)
        return path


class InterruptSignal:
    """Thread-safe cancellation flag."""
    def __init__(self):
        self._event = threading.Event()

    def set(self):
        self._event.set()

    def clear(self):
        self._event.clear()

    def is_set(self):
        return self._event.is_set()

    def check(self, msg="Operation cancelled by user."):
        if self._event.is_set():
            raise InterruptedError(msg)


INTERRUPT = InterruptSignal()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OllamaClient v7.2 — STREAMING + TRUE CANCEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OllamaClient:
    """
    Ollama client v7.2 with STREAMING mode and TRUE cancel.

    === WHY THIS FIXES THE 48-SECOND DELAY ===

    v7.1 problem:
      - Used stream=False (Ollama computes ENTIRE response before returning)
      - Cancel just stopped waiting, but Ollama kept the GPU busy
      - Next request queued behind the orphaned computation

    v7.2 fix:
      - stream=True: Ollama sends tokens as they're generated
      - On cancel: resp.close() → TCP RST → Ollama stops mid-generation
      - GPU is freed IMMEDIATELY, next request starts right away

    === SPEED OPTIMIZATIONS ===
      - Model: llama3.2:3b (3x faster than llama3 8B)
      - keep_alive=10m: no model reload between requests
      - Reduced context windows (512 for classify, 768 for vision)
      - History limited to 4 messages
      - Input truncation for classify (200 chars max)
    """

    def __init__(self, model=OLLAMA_MODEL, api_base=OLLAMA_API_BASE,
                 system_message="", classify_prompt=""):
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.system_message = system_message
        self.classify_prompt = classify_prompt
        self.history = []
        self._max_history = 10     # v8.0: increased from 4 for better chess/multi-turn context
        self._active_resp = None   # Active HTTP response (for abort)
        self._resp_lock = threading.Lock()

    # ── Force-abort active request ──

    def abort(self):
        """
        Force-close the active HTTP stream.
        This sends TCP RST to Ollama, which STOPS generation immediately.
        The GPU is freed and the next request can start.
        """
        with self._resp_lock:
            resp = self._active_resp
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
                self._active_resp = None

    def chat_stream(self, user_message, one_shot=False):
        """
        Full conversation mode with TOKEN YIELDING for real-time UI updates.
        v8.0: Removed 500 char truncation for better chess/context support.
        """
        # v8.0: No truncation for chat mode - needed for chess moves and long context

        messages = [{"role": "system", "content": self.system_message}]
        if not one_shot:
            self.history.append({"role": "user", "content": user_message})
            messages.extend(self.history[-self._max_history:])
        else:
            messages.append({"role": "user", "content": user_message})

        full_response = []
        for token in self._call_api_stream(
            messages,
            num_ctx=FULL_CONTEXT_WINDOW,
            num_predict=FULL_MAX_TOKENS,
            temperature=FULL_TEMPERATURE,
            timeout=90,
            top_k=FULL_TOP_K,
            top_p=FULL_TOP_P,
        ):
            full_response.append(token)
            yield token

        if not one_shot and full_response:
            self.history.append({"role": "assistant", "content": "".join(full_response)})

    def _call_api_stream(self, messages, num_ctx, num_predict, temperature, timeout=60, top_k=20, top_p=0.5):
        """
        Generator version of _call_api for real-time streaming.
        """
        INTERRUPT.check()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": num_ctx,
                "num_gpu": OLLAMA_NUM_GPU,
                "num_batch": 512,
                "num_thread": OLLAMA_NUM_THREAD,
                "top_k": top_k,
                "top_p": top_p,
            },
            "keep_alive": OLLAMA_KEEP_ALIVE,
        }

        resp = None
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.api_base}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=timeout)

            with self._resp_lock:
                self._active_resp = resp

            for raw_line in resp:
                if INTERRUPT.is_set():
                    break
                if not raw_line or not raw_line.strip():
                    continue
                try:
                    chunk = json.loads(raw_line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

                if chunk.get("done", False):
                    break
        finally:
            with self._resp_lock:
                self._active_resp = None
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass

    # ── Core API call (STREAMING) ──

    def _call_api(self, messages, num_ctx, num_predict, temperature, timeout=60, top_k=20, top_p=0.5):
        """
        STREAMING Ollama API call with TRUE interrupt.

        Architecture:
          1. POST /api/chat with stream=True in a daemon thread
          2. Thread reads response line-by-line, collecting chunks
          3. Main thread polls INTERRUPT every 150ms
          4. On cancel: abort() closes HTTP stream → Ollama stops GPU
          5. Thread detects closed stream, exits cleanly

        This is fundamentally different from v7.1:
          - v7.1: stream=False, orphan thread, GPU keeps computing
          - v7.2: stream=True, close stream, GPU stops immediately
        """
        INTERRUPT.check()

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": num_ctx,
                "num_gpu": OLLAMA_NUM_GPU,
                "num_batch": 512,
                "num_thread": OLLAMA_NUM_THREAD,
                "top_k": top_k,
                "top_p": top_p,
            },
            "keep_alive": OLLAMA_KEEP_ALIVE,
        }

        # Shared state between main thread and worker
        state = {
            "chunks": [],
            "error": None,
            "done": False,
        }

        def stream_worker():
            resp = None
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base}/api/chat",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=timeout)

                # Store reference so abort() can close it
                with self._resp_lock:
                    self._active_resp = resp

                # Read streaming response line by line
                for raw_line in resp:
                    if not raw_line or not raw_line.strip():
                        continue
                    try:
                        chunk = json.loads(raw_line.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue

                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        state["chunks"].append(content)

                    if chunk.get("done", False):
                        break

                state["done"] = True

            except Exception as e:
                # Don't record error if we intentionally aborted
                if not INTERRUPT.is_set():
                    state["error"] = e
            finally:
                with self._resp_lock:
                    self._active_resp = None
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass

        t = threading.Thread(target=stream_worker, daemon=True)
        t.start()

        # Poll every 150ms — faster reaction than v7.1's 200ms
        while t.is_alive():
            if INTERRUPT.is_set():
                # TRUE CANCEL: close the HTTP stream → Ollama stops
                self.abort()
                # Wait briefly for thread to notice and exit
                t.join(timeout=0.3)
                raise InterruptedError("Cancelled by user.")
            t.join(timeout=0.15)

        # Check for errors
        if state["error"] is not None:
            err = state["error"]
            if isinstance(err, urllib.error.URLError):
                raise ConnectionError(f"Cannot reach Ollama: {err}") from err
            if isinstance(err, urllib.error.HTTPError):
                raise ConnectionError(
                    f"Ollama HTTP {err.code}: {err.reason}"
                ) from err
            raise ConnectionError(f"Ollama error: {err}") from err

        text = "".join(state["chunks"]).strip()
        if not text and not state["done"]:
            raise ConnectionError("Ollama returned empty response.")

        return text

    # ── FAST classify (for PreRouter misses) ──

    def classify(self, user_message, max_user_chars=1000):
        """
        FAST classification: compact prompt, no self.history.
        Optional recent-dialog prefix may be passed in user_message (see dispatcher).
        """
        um = (user_message or "")[:max_user_chars]
        messages = [
            {"role": "system", "content": self.classify_prompt},
            {"role": "user", "content": um},
        ]
        return self._call_api(
            messages,
            num_ctx=max(FAST_CONTEXT_WINDOW, 1024),
            num_predict=FAST_MAX_TOKENS,
            temperature=FAST_TEMPERATURE,
            timeout=30,
            top_k=FAST_TOP_K,
            top_p=FAST_TOP_P,
        )

    # ── Full chat (conversations, code) ──

    def chat(self, user_message, one_shot=False):
        """
        Full conversation/code mode.

        v8.0 optimizations:
          - History increased to 10 messages (was 4) for better chess/context
          - Timeout 90s, GPU optimized
        """

        messages = [{"role": "system", "content": self.system_message}]

        if not one_shot:
            self.history.append({"role": "user", "content": user_message})
            messages.extend(self.history[-self._max_history:])
        else:
            messages.append({"role": "user", "content": user_message})

        result = self._call_api(
            messages,
            num_ctx=FULL_CONTEXT_WINDOW,
            num_predict=FULL_MAX_TOKENS,
            temperature=FULL_TEMPERATURE,
            timeout=90,
            top_k=FULL_TOP_K,
            top_p=FULL_TOP_P,
        )

        if not one_shot and result:
            self.history.append({"role": "assistant", "content": result})

        return result

    # ── Vision step (for agentic control loop) ──

    def vision_step(self, goal, screen_elements, previous_actions):
        """
        Single step of the Vision → Action loop.
        Ultra-fast: minimal context, zero temperature.

        Args:
            goal: what to achieve ("type hello in telegram")
            screen_elements: OCR results as compact string
            previous_actions: log of what was already done

        Returns:
            Raw LLM response (should be JSON action)
        """
        prompt = (
            f"Goal: {goal}\n"
            f"Screen: {screen_elements[:400]}\n"
            f"Done: {previous_actions[-150:] if previous_actions else 'none'}\n"
            "Reply ONLY with JSON:\n"
            '{"action":"click","target":"text on screen"}\n'
            '{"action":"type","text":"message"}\n'
            '{"action":"hotkey","keys":["ctrl","a"]}\n'
            '{"action":"scroll","clicks":3}\n'
            '{"action":"done","result":"what was achieved"}\n'
            '{"action":"fail","result":"why it failed"}'
        )
        messages = [
            {"role": "system",
             "content": "You control a Windows PC via mouse/keyboard. "
                        "You see OCR text from a screenshot. "
                        "Output ONLY one JSON action to get closer to the goal."},
            {"role": "user", "content": prompt},
        ]
        return self._call_api(
            messages,
            num_ctx=VISION_CONTEXT_WINDOW,
            num_predict=VISION_MAX_TOKENS,
            temperature=0.0,
            timeout=30,
            top_k=VISION_TOP_K,
            top_p=VISION_TOP_P,
        )

    # ── Warmup (pre-load model into VRAM) ──

    def warmup(self):
        """
        Pre-load model into GPU VRAM.
        Call once on startup to eliminate first-request delay.
        """
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "options": {
                    "num_predict": 1,
                    "num_ctx": 32,
                    "num_gpu": OLLAMA_NUM_GPU,
                },
                "keep_alive": OLLAMA_KEEP_ALIVE,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.api_base}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except Exception:
            pass  # Warmup failure is non-critical

    # ── Reset history ──

    def reset(self):
        self.history.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CodeExecutor — unchanged from v7.1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CodeExecutor:
    """Extract and execute Python code blocks in isolated subprocesses."""

    CODE_BLOCK_RE = re.compile(
        r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE
    )

    @classmethod
    def parse_response(cls, text):
        parts = []
        last_end = 0
        for m in cls.CODE_BLOCK_RE.finditer(text):
            before = text[last_end:m.start()].strip()
            if before:
                parts.append(("text", before))
            code = m.group(1).strip()
            if code:
                parts.append(("code", code))
            last_end = m.end()
        after = text[last_end:].strip()
        if after:
            parts.append(("text", after))
        return parts if parts else [("text", text.strip())]

    @classmethod
    def has_code(cls, text):
        return bool(cls.CODE_BLOCK_RE.search(text))

    @classmethod
    def execute(cls, code, timeout=CODE_EXEC_TIMEOUT):
        from .config import ALLOW_CODE_EXEC
        if not ALLOW_CODE_EXEC:
            return (
                False,
                "",
                "Выполнение кода из ответа ИИ отключено. "
                "Установите переменную окружения SOKOL_ALLOW_CODE_EXEC=1 для включения.",
            )
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False,
                encoding="utf-8", dir=tempfile.gettempdir(),
            ) as f:
                f.write("# -*- coding: utf-8 -*-\n")
                f.write(code)
                f.flush()
                tmp_path = f.name
            INTERRUPT.check()
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=NOWINDOW,
                cwd=os.path.expanduser("~"),
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", f"Execution timed out after {timeout}s."
        except InterruptedError:
            raise
        except Exception as e:
            return False, "", f"Execution error: {e}"
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
