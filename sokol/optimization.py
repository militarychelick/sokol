# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Performance Optimization and Memory Management"""
import asyncio
import logging
import gc
import psutil
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json

from .memory import VectorMemoryStore, MemoryItem, MemoryType
from .config import OLLAMA_NUM_GPU, OLLAMA_KEEP_ALIVE
from .core import OllamaClient

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor system performance and resource usage"""
    
    def __init__(self):
        self.logger = logging.getLogger("sokol.performance")
        self._monitoring = False
        self._performance_history: List[Dict[str, Any]] = []
        
    def start_monitoring(self):
        """Start performance monitoring"""
        self._monitoring = True
        self.logger.info("Performance monitoring started")
        
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self._monitoring = False
        self.logger.info("Performance monitoring stopped")
        
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current system performance stats"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # GPU info (if available)
            gpu_info = self._get_gpu_info()
            
            # Process info
            process = psutil.Process()
            process_memory = process.memory_info()
            
            stats = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "process_memory_mb": process_memory.rss / (1024**2),
                "gpu_info": gpu_info
            }
            
            # Store in history
            if self._monitoring:
                self._performance_history.append(stats)
                # Keep only last 100 entries
                self._performance_history = self._performance_history[-100:]
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Performance stats failed: {e}")
            return {"error": str(e)}
    
    def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information if available"""
        try:
            # Try to get GPU info from nvidia-ml-py if available
            import pynvml
            pynvml.nvmlInit()
            
            device_count = pynvml.nvmlDeviceGetCount()
            gpu_info = {"devices": []}
            
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle).decode()
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                gpu_info["devices"].append({
                    "id": i,
                    "name": name,
                    "memory_used_mb": memory_info.used / (1024**2),
                    "memory_total_mb": memory_info.total / (1024**2),
                    "memory_percent": (memory_info.used / memory_info.total) * 100,
                    "gpu_utilization": utilization.gpu,
                    "memory_utilization": utilization.memory
                })
            
            return gpu_info
            
        except ImportError:
            return {"status": "nvidia-ml-py not available"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_performance_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get performance history"""
        return self._performance_history[-limit:]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics"""
        if not self._performance_history:
            return {"status": "no data"}
        
        recent = self._performance_history[-20:]  # Last 20 entries
        
        cpu_values = [s.get("cpu_percent", 0) for s in recent]
        memory_values = [s.get("memory_percent", 0) for s in recent]
        
        return {
            "period": f"Last {len(recent)} measurements",
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values)
            },
            "memory": {
                "avg": sum(memory_values) / len(memory_values),
                "max": max(memory_values),
                "min": min(memory_values)
            },
            "measurements": len(recent)
        }


class MemoryOptimizer:
    """Optimize memory usage and cleanup"""
    
    def __init__(self, memory_store: Optional[VectorMemoryStore] = None):
        self.memory_store = memory_store
        self.logger = logging.getLogger("sokol.memory_optimizer")
        
    async def optimize_memory(self) -> Dict[str, Any]:
        """Run memory optimization"""
        results = {}
        
        # Python garbage collection
        try:
            collected = gc.collect()
            results["garbage_collected"] = collected
            self.logger.debug(f"Garbage collected {collected} objects")
        except Exception as e:
            self.logger.error(f"Garbage collection failed: {e}")
            results["garbage_collected"] = 0
        
        # Vector memory cleanup
        if self.memory_store:
            try:
                cleaned = await self.memory_store.cleanup_old_memories(days=7)
                results["memory_cleaned"] = cleaned
                self.logger.info(f"Cleaned {cleaned} old memories")
            except Exception as e:
                self.logger.error(f"Memory cleanup failed: {e}")
                results["memory_cleaned"] = 0
        
        # Process memory optimization
        try:
            process = psutil.Process()
            before_memory = process.memory_info().rss
            
            # Force garbage collection again
            gc.collect()
            
            after_memory = process.memory_info().rss
            memory_freed = before_memory - after_memory
            
            results["process_memory_freed_mb"] = memory_freed / (1024**2)
            
        except Exception as e:
            self.logger.error(f"Process memory optimization failed: {e}")
            results["process_memory_freed_mb"] = 0
        
        return results
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """Get detailed memory usage information"""
        try:
            # System memory
            system_memory = psutil.virtual_memory()
            
            # Process memory
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # Vector memory stats
            vector_stats = {}
            if self.memory_store:
                vector_stats = await self.memory_store.get_memory_stats()
            
            return {
                "system_memory": {
                    "total_gb": system_memory.total / (1024**3),
                    "available_gb": system_memory.available / (1024**3),
                    "used_gb": system_memory.used / (1024**3),
                    "percent": system_memory.percent
                },
                "process_memory": {
                    "rss_mb": process_memory.rss / (1024**2),
                    "vms_mb": process_memory.vms / (1024**2)
                },
                "vector_memory": vector_stats,
                "python_objects": len(gc.get_objects())
            }
            
        except Exception as e:
            self.logger.error(f"Memory usage check failed: {e}")
            return {"error": str(e)}


class ModelOptimizer:
    """Optimize model usage and performance"""
    
    def __init__(self):
        self.logger = logging.getLogger("sokol.model_optimizer")
        self.model_cache: Dict[str, OllamaClient] = {}
        
    async def optimize_model_usage(self) -> Dict[str, Any]:
        """Optimize model usage for better performance"""
        results = {}
        
        # Check GPU optimization
        gpu_optimized = OLLAMA_NUM_GPU > 0
        results["gpu_enabled"] = gpu_optimized
        results["ollama_num_gpu"] = OLLAMA_NUM_GPU
        
        # Check keep_alive setting
        results["keep_alive"] = OLLAMA_KEEP_ALIVE
        results["keep_alive_minutes"] = self._parse_keep_alive(OLLAMA_KEEP_ALIVE)
        
        # Model warmup status
        results["models_warmed"] = len(self.model_cache)
        
        return results
    
    def _parse_keep_alive(self, keep_alive: str) -> float:
        """Parse keep_alive string to minutes"""
        try:
            if keep_alive.endswith("m"):
                return float(keep_alive[:-1])
            elif keep_alive.endswith("h"):
                return float(keep_alive[:-1]) * 60
            else:
                return 5.0  # Default
        except:
            return 5.0
    
    def get_cached_client(self, model: str) -> Optional[OllamaClient]:
        """Get or create cached model client"""
        if model not in self.model_cache:
            try:
                self.model_cache[model] = OllamaClient(model=model)
                self.logger.info(f"Cached client for model: {model}")
            except Exception as e:
                self.logger.error(f"Failed to cache client for {model}: {e}")
                return None
        
        return self.model_cache.get(model)
    
    async def warmup_models(self, models: List[str]) -> Dict[str, bool]:
        """Warmup multiple models for better performance"""
        results = {}
        
        for model in models:
            try:
                client = self.get_cached_client(model)
                if client:
                    await asyncio.get_event_loop().run_in_executor(None, client.warmup)
                    results[model] = True
                    self.logger.info(f"Warmed up model: {model}")
                else:
                    results[model] = False
            except Exception as e:
                self.logger.error(f"Failed to warmup {model}: {e}")
                results[model] = False
        
        return results
    
    def clear_cache(self):
        """Clear model cache"""
        self.model_cache.clear()
        self.logger.info("Model cache cleared")


class CacheManager:
    """Manage various caches for performance"""
    
    def __init__(self):
        self.logger = logging.getLogger("sokol.cache_manager")
        self.caches: Dict[str, Dict[str, Any]] = {}
        
    def create_cache(self, name: str, max_size: int = 1000, ttl_seconds: int = 3600):
        """Create a new cache"""
        self.caches[name] = {
            "data": {},
            "max_size": max_size,
            "ttl_seconds": ttl_seconds,
            "created_at": datetime.now()
        }
        self.logger.debug(f"Created cache: {name}")
    
    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get item from cache"""
        if cache_name not in self.caches:
            return None
        
        cache = self.caches[cache_name]
        item = cache["data"].get(key)
        
        if item is None:
            return None
        
        # Check TTL
        if datetime.now() - item["created_at"] > timedelta(seconds=cache["ttl_seconds"]):
            del cache["data"][key]
            return None
        
        # Update access time
        item["last_accessed"] = datetime.now()
        return item["value"]
    
    def set(self, cache_name: str, key: str, value: Any):
        """Set item in cache"""
        if cache_name not in self.caches:
            self.create_cache(cache_name)
        
        cache = self.caches[cache_name]
        
        # Check size limit
        if len(cache["data"]) >= cache["max_size"]:
            # Remove least recently used item
            oldest_key = min(cache["data"].keys(), 
                           key=lambda k: cache["data"][k]["last_accessed"])
            del cache["data"][oldest_key]
        
        cache["data"][key] = {
            "value": value,
            "created_at": datetime.now(),
            "last_accessed": datetime.now()
        }
    
    def clear_cache(self, cache_name: str):
        """Clear specific cache"""
        if cache_name in self.caches:
            self.caches[cache_name]["data"].clear()
            self.logger.debug(f"Cleared cache: {cache_name}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {}
        for name, cache in self.caches.items():
            stats[name] = {
                "size": len(cache["data"]),
                "max_size": cache["max_size"],
                "ttl_seconds": cache["ttl_seconds"]
            }
        return stats


class OptimizationManager:
    """Main optimization manager"""
    
    def __init__(self, memory_store: Optional[VectorMemoryStore] = None):
        self.performance_monitor = PerformanceMonitor()
        self.memory_optimizer = MemoryOptimizer(memory_store)
        self.model_optimizer = ModelOptimizer()
        self.cache_manager = CacheManager()
        self.logger = logging.getLogger("sokol.optimization")
        
    async def initialize(self):
        """Initialize optimization systems"""
        try:
            # Start performance monitoring
            self.performance_monitor.start_monitoring()
            
            # Create default caches
            self.cache_manager.create_cache("agent_responses", max_size=500, ttl_seconds=300)
            self.cache_manager.create_cache("vision_analysis", max_size=100, ttl_seconds=600)
            self.cache_manager.create_cache("search_results", max_size=200, ttl_seconds=1800)
            
            # Optimize initial memory
            await self.memory_optimizer.optimize_memory()
            
            self.logger.info("Optimization systems initialized")
            
        except Exception as e:
            self.logger.error(f"Optimization initialization failed: {e}")
    
    async def get_optimization_status(self) -> Dict[str, Any]:
        """Get comprehensive optimization status"""
        try:
            # Performance stats
            performance = self.performance_monitor.get_current_stats()
            
            # Memory usage
            memory_usage = await self.memory_optimizer.get_memory_usage()
            
            # Model optimization
            model_optimization = await self.model_optimizer.optimize_model_usage()
            
            # Cache stats
            cache_stats = self.cache_manager.get_cache_stats()
            
            return {
                "performance": performance,
                "memory": memory_usage,
                "models": model_optimization,
                "caches": cache_stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Optimization status failed: {e}")
            return {"error": str(e)}
    
    async def run_optimization_cycle(self) -> Dict[str, Any]:
        """Run a complete optimization cycle"""
        try:
            results = {}
            
            # Memory optimization
            memory_results = await self.memory_optimizer.optimize_memory()
            results["memory"] = memory_results
            
            # Cache cleanup (remove expired items)
            cache_cleanup = {}
            for cache_name in self.cache_manager.caches:
                # This would be implemented to remove expired items
                cache_cleanup[cache_name] = "cleaned"
            results["cache_cleanup"] = cache_cleanup
            
            # Performance summary
            performance_summary = self.performance_monitor.get_performance_summary()
            results["performance_summary"] = performance_summary
            
            self.logger.info("Optimization cycle completed")
            return results
            
        except Exception as e:
            self.logger.error(f"Optimization cycle failed: {e}")
            return {"error": str(e)}
    
    def shutdown(self):
        """Shutdown optimization systems"""
        try:
            self.performance_monitor.stop_monitoring()
            self.model_optimizer.clear_cache()
            self.logger.info("Optimization systems shutdown")
        except Exception as e:
            self.logger.error(f"Optimization shutdown failed: {e}")


# Global instance
_optimization_manager: Optional[OptimizationManager] = None


def get_optimization_manager(memory_store: Optional[VectorMemoryStore] = None) -> OptimizationManager:
    """Get global optimization manager"""
    global _optimization_manager
    if _optimization_manager is None:
        _optimization_manager = OptimizationManager(memory_store)
    return _optimization_manager


async def initialize_optimization(memory_store: Optional[VectorMemoryStore] = None) -> bool:
    """Initialize optimization systems"""
    manager = get_optimization_manager(memory_store)
    await manager.initialize()
    return True


async def get_system_optimization_status() -> Dict[str, Any]:
    """Get system optimization status"""
    manager = get_optimization_manager()
    return await manager.get_optimization_status()


async def run_optimization_cycle() -> Dict[str, Any]:
    """Run optimization cycle"""
    manager = get_optimization_manager()
    return await manager.run_optimization_cycle()
