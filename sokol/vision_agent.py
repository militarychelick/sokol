# -*- coding: utf-8 -*-
"""VisionAgent: OCR + LLM step loop for GUI automation."""
import json
import re
import time

from .config import VISION_MAX_STEPS, VISION_STEP_DELAY
from .core import INTERRUPT
from .automation import GUIAutomation, VisionLite
from .tools import SmartLauncher

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VisionAgent — Vision → Action loop for GUI automation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VisionAgent:
    """
    Autonomous GUI control via screenshot OCR + LLM decisions.

    Cycle:
      1. Take screenshot → OCR → list of UI elements with coordinates
      2. Send goal + elements to LLM → get JSON action
      3. Execute action (click, type, hotkey, scroll)
      4. Wait for UI update → repeat

    Use cases:
      - "напиши в телеграм привет" → focus Telegram, find input, type, send
      - "нарисуй круг в пейнте" → focus Paint, select tool, draw
      - "открой настройки в хроме" → find menu, click Settings
    """

    @classmethod
    def _safe_int(cls, value, default=0):
        try:
            if isinstance(value, bool):
                return default
            return int(float(str(value).strip().replace(",", ".")))
        except Exception:
            return default

    @classmethod
    def run(cls, goal, app_name=None, llm=None, gui=None):
        """
        Execute a multi-step GUI task using vision.

        Args:
            goal:     Natural language goal ("type hello in chat")
            app_name: App to focus first (translated name, e.g. "telegram")
            llm:      OllamaClient instance (for vision_step calls)
            gui:      GUI reference (for memory recording)

        Returns:
            (success: bool, message: str)
        """
        if not VisionLite._get_reader():
            return False, (
                "VisionAgent requires EasyOCR + PyAutoGUI.\n"
                "Install: pip install easyocr pyautogui numpy"
            )

        # Step 0: Focus target app
        if app_name:
            ok, msg, _ = SmartLauncher.launch(app_name)
            if not ok:
                return False, f"Cannot open {app_name}: {msg}"
            time.sleep(1.5)  # Wait for app to appear

        action_log = []

        for step in range(VISION_MAX_STEPS):
            INTERRUPT.check()

            # 1. Screenshot + OCR
            ok, msg, elements = VisionLite.ocr_screen()
            if not ok:
                return False, f"Vision failed at step {step}: {msg}"

            if not elements:
                action_log.append(f"step{step}: no text on screen")
                time.sleep(0.5)
                continue

            # 2. Compact screen description for LLM
            screen_summary = ", ".join(
                f'"{e["text"]}"@({e["x"]},{e["y"]})'
                for e in elements[:25]  # Top 25 elements
            )

            log_summary = "; ".join(action_log[-3:]) if action_log else "none"

            # 3. Ask LLM for next action
            try:
                response = llm.vision_step(goal, screen_summary, log_summary)
            except InterruptedError:
                raise
            except Exception as e:
                action_log.append(f"step{step}: LLM error: {e}")
                continue

            action = cls._parse_action(response)
            if not action:
                action_log.append(f"step{step}: invalid LLM output")
                continue

            # 4. Execute the action
            act = action.get("action", "")

            if act == "done":
                result = action.get("result", "Goal achieved.")
                return True, f"✓ {result}\n[{step+1} steps: {'; '.join(action_log[-5:])}]"

            if act == "fail":
                result = action.get("result", "Goal failed.")
                return False, f"✗ {result}\n[{step+1} steps: {'; '.join(action_log[-5:])}]"

            if act == "click":
                target = action.get("target", "")
                ok, msg = VisionLite.click_text(target)
                action_log.append(
                    f"click '{target}': {'ok' if ok else msg[:30]}"
                )

            elif act == "type":
                text = action.get("text", "")
                if any(ord(c) > 127 for c in text):
                    ok, msg = GUIAutomation.type_unicode(text)
                else:
                    ok, msg = GUIAutomation.type_text(text)
                action_log.append(
                    f"type '{text[:20]}': {'ok' if ok else msg[:30]}"
                )

            elif act == "hotkey":
                keys = action.get("keys", [])
                if keys:
                    ok, msg = GUIAutomation.hotkey(*keys)
                    action_log.append(f"hotkey {'+'.join(keys)}: ok")
                else:
                    action_log.append(f"step{step}: empty hotkey")

            elif act == "scroll":
                clicks = cls._safe_int(action.get("clicks", 3), 3)
                ok, msg = GUIAutomation.scroll(clicks)
                direction = "up" if clicks > 0 else "down"
                action_log.append(
                    f"scroll {direction}: {'ok' if ok else msg[:30]}"
                )

            elif act == "double_click":
                target = action.get("target", "")
                ok_find, msg_find, item = VisionLite.find_text_on_screen(target)
                if ok_find and item:
                    ok, msg = GUIAutomation.double_click(item["x"], item["y"])
                    action_log.append(f"dblclick '{target}': ok")
                else:
                    action_log.append(f"dblclick '{target}': not found")

            elif act == "right_click":
                target = action.get("target", "")
                ok_find, msg_find, item = VisionLite.find_text_on_screen(target)
                if ok_find and item:
                    ok, msg = GUIAutomation.right_click(item["x"], item["y"])
                    action_log.append(f"rclick '{target}': ok")
                else:
                    action_log.append(f"rclick '{target}': not found")

            elif act == "move":
                x = cls._safe_int(action.get("x", 0), 0)
                y = cls._safe_int(action.get("y", 0), 0)
                ok, msg = GUIAutomation.move_to(x, y)
                action_log.append(
                    f"move ({x},{y}): {'ok' if ok else msg[:30]}"
                )

            elif act == "drag":
                x = cls._safe_int(action.get("x", 0), 0)
                y = cls._safe_int(action.get("y", 0), 0)
                ok, msg = GUIAutomation.drag_to(x, y)
                action_log.append(
                    f"drag ({x},{y}): {'ok' if ok else msg[:30]}"
                )

            else:
                action_log.append(f"step{step}: unknown action '{act}'")

            # Wait for UI to update before next screenshot
            time.sleep(VISION_STEP_DELAY)

        return False, (
            f"Max steps ({VISION_MAX_STEPS}) reached.\n"
            f"Actions: {'; '.join(action_log)}"
        )

    @classmethod
    def _parse_action(cls, text):
        """Extract JSON action from LLM response."""
        if not text:
            return None
        text = text.strip()
        try:
            # Direct JSON
            if text.startswith("{"):
                return json.loads(text)
            # JSON embedded in text
            m = re.search(r'\{[^{}]*\}', text)
            if m:
                return json.loads(m.group(0))
            # JSON with nested arrays (for keys)
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None
