# ROCm Setup for AMD RX 5700 XT
## Пошаговая инструкция без воды

### Шаг 1: Проверка совместимости
RX 5700 XT использует архитектуру RDNA (Navi 10).
ROCm официально поддерживает RDNA2+, НО есть обход для RDNA1.

### Шаг 2: Установка Ollama с ROCm
```powershell
# 1. Удалить старую версию Ollama
sc stop ollama
sc delete ollama
rmdir /s /q "%LOCALAPPDATA%\Programs\Ollama"

# 2. Скачать ROCm версию (НЕ обычную!)
# Ссылка: https://github.com/ollama/ollama/releases
# Файл: ollama-windows-amd64-rocm.zip (или .exe с rocm в названии)

# 3. Установить
# Распаковать в C:\Program Files\Ollama
# Или запустить инсталлятор с ROCm

# 4. Настройка переменных сред
setx OLLAMA_NUM_GPU 1
setx HSA_OVERRIDE_GFX_VERSION 10.1.0  # Ключевая переменная для RX 5700 XT!

# 5. Перезагрузка
shutdown /r /t 0
```

### Шаг 3: Проверка после установки
```powershell
# Открыть PowerShell от админа
ollama --version
ollama ps  # Должен показать GPU
# Если GPU не показывает - смотри логи:
# %LOCALAPPDATA%\Ollama\logs\server.log
```

### Шаг 4: Тест
```powershell
ollama run qwen2.5:1.5b
# В другом окне:
ollama ps
# Должно быть: 100% GPU, не CPU
```

### Troubleshooting
Если не работает:
1. Проверь драйвер AMD - должен быть 23.12.1 или новее
2. Проверь HSA_OVERRIDE_GFX_VERSION=10.1.0
3. Проверь что Ollama запущен: services.msc → Ollama
4. Логи: type "%LOCALAPPDATA%\Ollama\logs\server.log" | findstr GPU

### Альтернатива (если ROCm не заведётся)
Использовать llama.cpp с Vulkan:
```powershell
# Скачать: https://github.com/ggerganov/llama.cpp/releases
# Запускать с --gpu-layers 35
```
