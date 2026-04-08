# -*- coding: utf-8 -*-
"""SOKOL v8.0 - GPU Monitor and Fix Script"""
import os
import subprocess
import time
import psutil

def restart_ollama_with_gpu():
    """Restart Ollama with proper GPU settings"""
    print("Restarting Ollama with GPU support...")
    
    # Kill existing Ollama processes
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"], capture_output=True)
        time.sleep(2)
    except:
        pass
    
    # Set environment variables for AMD GPU
    env = os.environ.copy()
    env.update({
        "OLLAMA_NUM_GPU": "1",
        "OLLAMA_MAX_LOADED_MODELS": "1",
        "SOKOL_GPU_BACKEND": "rocm",
        "HSA_OVERRIDE_GFX_VERSION": "10.1.0",  # RX 5700 XT gfx1010
        "GPU_MAX_ALLOC_PERCENT": "100",
        "OLLAMA_GPU_OVERHEAD": "0",
        "HIP_VISIBLE_DEVICES": "0"
    })
    
    # Start Ollama with GPU
    try:
        subprocess.Popen(["ollama", "serve"], env=env, shell=True)
        time.sleep(5)
        print("Ollama restarted with GPU support")
    except Exception as e:
        print(f"Failed to restart Ollama: {e}")

def check_gpu_usage():
    """Check GPU and CPU usage"""
    try:
        # Check Ollama processes
        result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
        print("Ollama Status:")
        print(result.stdout)
        
        # Check system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        print(f"\nSystem Resources:")
        print(f"CPU: {cpu_percent:.1f}%")
        print(f"Memory: {memory.percent:.1f}%")
        
        # Try to get GPU info (AMD)
        try:
            result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"], 
                                  capture_output=True, text=True)
            if "AMD" in result.stdout:
                print("GPU: AMD detected (monitoring not available in Windows)")
            elif "NVIDIA" in result.stdout:
                # Try nvidia-smi for NVIDIA
                try:
                    result = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", 
                                           "--format=csv,noheader,nounits"], capture_output=True, text=True)
                    if result.returncode == 0:
                        gpu_util, mem_used, mem_total = result.stdout.strip().split(", ")
                        print(f"GPU: {gpu_util}% utilization, {mem_used}/{mem_total} MB memory")
                except:
                    print("GPU: NVIDIA detected but nvidia-smi not available")
        except:
            print("GPU: Could not detect GPU information")
            
    except Exception as e:
        print(f"GPU check failed: {e}")

def fix_gpu_acceleration():
    """Fix GPU acceleration issues"""
    print("Fixing GPU acceleration...")
    
    # Check current model
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "qwen2.5:1.5b" not in result.stdout:
            print("Pulling qwen2.5:1.5b for better AMD GPU support...")
            subprocess.run(["ollama", "pull", "qwen2.5:1.5b"])
        
        # Stop current model
        subprocess.run(["ollama", "stop"], capture_output=True)
        
        # Restart with GPU
        restart_ollama_with_gpu()
        
        # Test GPU usage
        time.sleep(3)
        check_gpu_usage()
        
    except Exception as e:
        print(f"GPU fix failed: {e}")

if __name__ == "__main__":
    print("SOKOL v8.0 - GPU Monitor and Fix")
    print("=" * 40)
    
    fix_gpu_acceleration()
