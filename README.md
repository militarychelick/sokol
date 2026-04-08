# SOKOL

Локальный ИИ-ассистент для Windows (Ollama).

## Быстрый старт

1. Создайте venv и активируйте его.
2. Установите зависимости (обязательно, иначе будет `No module named 'pydantic'`):

   ```powershell
   pip install -r requirements.txt
   ```

   Или: `.\scripts\bootstrap_venv.ps1` / `scripts\install_deps.bat`

3. Установите [Ollama](https://ollama.com) и модель из `sokol/config.py` (например `ollama pull llama3.2:3b`).
4. Запуск:

   ```text
   python run.py
   ```

   Если Windows блокирует повышение прав для `venv\Scripts\python.exe` (UAC / Smart App Control, код 5), используйте:

   ```text
   python run.py --skip-admin-check
   ```

   или переменную окружения `SOKOL_SKIP_ELEVATION=1` (не показывать запрос UAC и не пытаться повысить права).

При ошибке elevation с **кодом 5** в консоли см. подсказку `[AdminHelper]` — это обычно блокировка доверенного запуска для интерпретатора из `venv`.

## Опционально: шахматы

Для партий лучше отдельный движок (Stockfish, сайт с API): Сокол может только открыть его или вызвать скрипт. Для проверки ходов в коде: модуль `sokol.chess_helpers` — `pip install chess` или `pip install ".[chess]"`.

## GPU и скорость Ollama

Сокол передаёт в Ollama `num_gpu` (по умолчанию все слои). Если в `ollama ps` модель на **CPU**, установите сборку Ollama с **CUDA** (NVIDIA) или **ROCm** (AMD) с сайта ollama.com и актуальные драйверы. Переменная **`OLLAMA_NUM_GPU`**: `99` — все слои на GPU, `0` — принудительно CPU. Для EasyOCR: **`SOKOL_EASYOCR_GPU=1`** или **`0`** (иначе CUDA включается, если доступна).

## Модели и внешние API

Сменить модель: `OLLAMA_MODEL` в `sokol/config.py` или свой `Modelfile`. Быстрее/умнее локально — пробуйте `qwen2.5`, `mistral`, `llama3.1` (тяжелее по VRAM). Стабильного «бесплатного облака уровня платного» нет; для опционального облака нужен свой ключ (Groq, OpenRouter и т.д.) и отдельная ветка в коде.

## Права администратора

Полный доступ к системным операциям требует админа. Повышение через UAC для интерпретатора из venv иногда **блокируется политикой** («издатель неизвестен»). Варианты: запуск без админа (`--skip-admin-check`), системный Python с python.org, или настройка Smart App Control у администратора ПК.
