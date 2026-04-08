# -*- coding: utf-8 -*-
"""SOKOL v8.0 - AMD GPU Launch Script for RX 5700 XT"""
import os
import subprocess
import sys

def setup_amd_gpu():
    """Setup environment variables for AMD GPU (ROCm)"""
    env_vars = {
        "SOKOL_GPU_BACKEND": "rocm",
        "OLLAMA_NUM_GPU": "1",  # Use 1 GPU layer for AMD
        "HSA_OVERRIDE_GFX_VERSION": "10.1.0",  # RX 5700 XT gfx1010
        "GPU_MAX_ALLOC_PERCENT": "100",
        "OLLAMA_GPU_OVERHEAD": "0",
        "HIP_VISIBLE_DEVICES": "0",
        "OLLAMA_MAX_LOADED_MODELS": "1"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"Set {key}={value}")

def check_gpu_status():
    """Check GPU status with Ollama"""
    try:
        result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
        print("Ollama GPU Status:")
        print(result.stdout)
        
        if "GPU" in result.stdout:
            print("â\x9c\x93 GPU acceleration detected!")
        else:
            print("â\x9c\x97 Using CPU only")
            
    except Exception as e:
        print(f"GPU check failed: {e}")

def main():
    print("SOKOL v8.0 - AMD GPU Launcher")
    print("="*50)
    
    # Setup AMD GPU environment
    print("Setting up AMD GPU environment...")
    setup_amd_gpu()
    
    # Check GPU status
    print("\nChecking GPU status...")
    check_gpu_status()
    
    # Launch SOKOL
    print("\nLaunching SOKOL with AMD GPU support...")
    try:
        subprocess.run([sys.executable, "run.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Launch failed: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user")

if __name__ == "__main__":
    main()
