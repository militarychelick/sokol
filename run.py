# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Enhanced Launch Script with Auto GPU Detection"""
import os
import sys
import time
import traceback
import subprocess
from datetime import datetime

print("[SOKOL] Starting...")

_LOG_DIR = os.path.join(os.path.dirname(__file__), "sokol")
_ERROR_LOG = os.path.join(_LOG_DIR, "sokol_error.log")


def _append_error_log(title: str, exc: BaseException | None = None) -> None:
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(_ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n{datetime.now().isoformat()} {title}\n")
            if exc is not None:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
            else:
                f.write("(no exception object)\n")
    except OSError:
        pass


def detect_gpu():
    """Auto-detect GPU and set appropriate environment variables"""
    print("[SOKOL] Detecting GPU...")
    
    # Check for NVIDIA GPU
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("[SOKOL] NVIDIA GPU detected")
            os.environ["SOKOL_GPU_BACKEND"] = "cuda"
            os.environ["CUDA_VISIBLE_DEVICES"] = "0"
            os.environ["OLLAMA_NUM_GPU"] = "1"
            return "nvidia"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Check for AMD GPU
    try:
        # Try to detect AMD GPU through ROCm or Windows GPU info
        result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and "AMD" in result.stdout.upper():
            print("[SOKOL] AMD GPU detected")
            os.environ["SOKOL_GPU_BACKEND"] = "rocm"
            os.environ["HSA_OVERRIDE_GFX_VERSION"] = "10.1.0"  # RX 5700 XT gfx1010
            os.environ["GPU_MAX_ALLOC_PERCENT"] = "100"
            os.environ["OLLAMA_GPU_OVERHEAD"] = "0"
            os.environ["HIP_VISIBLE_DEVICES"] = "0"
            os.environ["OLLAMA_NUM_GPU"] = "1"
            return "amd"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Check if Ollama is using GPU
    try:
        result = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and "GPU" in result.stdout:
            print("[SOKOL] Ollama GPU acceleration detected")
            return "gpu_detected"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    print("[SOKOL] No GPU detected or GPU not available - using CPU")
    os.environ["SOKOL_GPU_BACKEND"] = "cpu"
    os.environ["OLLAMA_NUM_GPU"] = "0"
    return "cpu"


def setup_optimization():
    """Setup performance optimization variables"""
    print("[SOKOL] Setting up optimization...")
    
    # General Ollama optimization
    os.environ["OLLAMA_FLASH_ATTENTION"] = "1"
    os.environ["OLLAMA_NUM_PARALLEL"] = "1"
    os.environ["OLLAMA_MAX_LOADED_MODELS"] = "1"
    os.environ["OLLAMA_KEEP_ALIVE"] = "10m"
    
    # Network optimization
    os.environ["no_proxy"] = "localhost,127.0.0.1"
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"
    os.environ["OPENAI_API_KEY"] = "sk-dummy-not-needed"
    
    print("[SOKOL] Optimization variables set")


def check_ollama_status():
    """Check Ollama status and models"""
    print("[SOKOL] Checking Ollama status...")
    
    try:
        # Check if Ollama is running
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print("[SOKOL] Ollama not running - starting Ollama...")
            subprocess.Popen(["ollama", "serve"], shell=True)
            time.sleep(3)  # Give Ollama time to start
        
        # Check available models
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            models = [line.split()[0] for line in result.stdout.split('\n') if line.strip() and not line.startswith('NAME')]
            if models:
                print(f"[SOKOL] Available models: {', '.join(models)}")
                
                # Set default model based on GPU
                gpu_type = detect_gpu()
                if gpu_type == "amd" and "qwen2.5:1.5b" in models:
                    os.environ["OLLAMA_MODEL"] = "qwen2.5:1.5b"
                    print("[SOKOL] Using qwen2.5:1.5b for AMD GPU")
                elif "llama3.2:3b" in models:
                    os.environ["OLLAMA_MODEL"] = "llama3.2:3b"
                    print("[SOKOL] Using llama3.2:3b")
                else:
                    os.environ["OLLAMA_MODEL"] = models[0]
                    print(f"[SOKOL] Using {models[0]}")
            else:
                print("[SOKOL] No models found - please run: ollama pull qwen2.5:1.5b")
    except Exception as e:
        print(f"[SOKOL] Ollama check failed: {e}")


_skip_elevation = os.environ.get("SOKOL_SKIP_ELEVATION", "").strip().lower() in (
    "1", "true", "yes", "on",
) or "--no-admin" in sys.argv  # Add --no-admin flag

# Setup GPU and optimization BEFORE admin check
setup_optimization()
check_ollama_status()

# Check admin rights AFTER GPU setup - but make it optional for GUI
if '--skip-admin-check' not in sys.argv and not _skip_elevation:
    try:
        from sokol.core import AdminHelper

        is_admin = AdminHelper.is_admin()
        print(f"[SOKOL] Admin check: is_admin={is_admin}")

        if '--admin-elevated' in sys.argv:
            print("[SOKOL] Running as elevated process (with admin rights)")
        elif not is_admin:
            print("[SOKOL] Not running as admin")
            print("[SOKOL] GUI will work without admin rights (limited system operations)")
            print("[SOKOL] Use --no-admin flag to skip this check entirely")
            # Don't try to elevate for GUI - just continue
            print("[SOKOL] Continuing without admin elevation...")
        else:
            print("[SOKOL] Already running with admin rights")
    except Exception as e:
        print(f"[SOKOL] Warning: Could not check admin rights: {e}")
        print("[SOKOL] Continuing without admin check...")
else:
    if _skip_elevation:
        print("[SOKOL] Admin elevation skipped")
    else:
        print("[SOKOL] Admin check skipped")

print("[SOKOL] Loading main module...")
try:
    from sokol.main import main
except ImportError as e:
    print(f"[SOKOL] Import error: {e}")
    print("[SOKOL] Make sure all dependencies are installed:")
    print("  pip install pydantic chromadb sentence-transformers keyboard psutil pynvml")
    time.sleep(5)
    sys.exit(1)

if __name__ == "__main__":
    try:
        print("[SOKOL] Starting SOKOL v8.0 Multi-Agent System...")
        main()
    except Exception as e:
        print(f"[SOKOL] Fatal error: {e}")
        traceback.print_exc()
        _append_error_log("Fatal error in main()", e)
        print("[SOKOL] Check error log for details")
        time.sleep(5)  # Keep window open to see error
        sys.exit(1)
