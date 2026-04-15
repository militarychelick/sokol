"""Continuous chaos runner for Validation & Hardening."""

import time
import random
from typing import Any, Dict, List


class ContinuousChaosRunner:
    """
    Continuous chaos runner for stress testing the system.
    
    Not a test suite - a destructive runner that breaks the system
    with random chaos and observes behavior over time.
    
    Chaos types:
    - Burst events (random spikes)
    - Emergency events during stress
    - Continuous load
    - Random timing
    """
    
    def __init__(self, live_loop_controller, seed: int = 42):
        """
        Initialize continuous chaos runner.
        
        Args:
            live_loop_controller: LiveLoopController instance to stress
        """
        self._controller = live_loop_controller
        self._running = False
        self._metrics_history = []
        self._rng = random.Random(seed)
        self._seed = seed
        self._fault_injections = {
            "tool_failures": 0,
            "latency_injections": 0,
            "memory_corruption_simulations": 0,
        }
    
    def run_destructive_test(self, duration_hours: int = 6, max_iterations: int | None = None) -> Dict[str, Any]:
        """
        Run continuous destructive test (6-24 hours).
        
        Args:
            duration_hours: Duration in hours
        
        Returns:
            Dictionary with metrics and observations
        """
        start_time = time.time()
        end_time = start_time + (duration_hours * 3600)
        
        print(f"Starting continuous destructive test for {duration_hours} hours")
        self._running = True
        
        iteration = 0
        while time.time() < end_time and self._running:
            if max_iterations is not None and iteration >= max_iterations:
                break
            iteration += 1
            # Random chaos: burst events
            if self._rng.random() < 0.1:  # 10% chance of burst
                self._inject_burst()
            
            # Random chaos: emergency during stress
            if self._rng.random() < 0.01:  # 1% chance of emergency
                self._inject_emergency()

            # Random chaos: tool failure injection signal
            if self._rng.random() < 0.08:
                self._inject_tool_failure()

            # Random chaos: latency injection
            if self._rng.random() < 0.08:
                self._inject_latency()

            # Random chaos: logical memory corruption simulation (contract-safe)
            if self._rng.random() < 0.03:
                self._simulate_memory_corruption()
            
            # Continuous load: normal events
            self._controller.submit_text(f"chaos test {int(time.time())}")
            
            # Collect metrics every 5 iterations (deterministic in bounded runs)
            if iteration % 5 == 0:
                metrics = self._collect_metrics()
                self._metrics_history.append(metrics)
                print(f"Metrics collected: {metrics}")
            
            # Random sleep (50-500ms)
            time.sleep(self._rng.uniform(0.01, 0.05))
        
        duration = time.time() - start_time
        
        return {
            "test_name": f"continuous_chaos_{duration_hours}h",
            "status": "completed" if self._running else "interrupted",
            "duration_seconds": duration,
            "seed": self._seed,
            "fault_injections": self._fault_injections,
            "metrics_history": self._metrics_history,
            "observations": self._analyze_behavior()
        }
    
    def _inject_burst(self) -> None:
        """Inject burst of events."""
        burst_size = self._rng.randint(10, 50)
        for i in range(burst_size):
            self._controller.submit_text(f"burst event {i}")
            time.sleep(0.01)  # 10ms between events
        print(f"Burst injected: {burst_size} events")
    
    def _inject_emergency(self) -> None:
        """Inject emergency event during stress."""
        emergency_commands = ["emergency stop", "/emergency", "sokol emergency stop"]
        cmd = self._rng.choice(emergency_commands)
        self._controller.submit_text(cmd)
        print(f"Emergency injected: {cmd}")

    def _inject_tool_failure(self) -> None:
        """Inject deterministic tool failure request signal."""
        self._fault_injections["tool_failures"] += 1
        self._controller.submit_text("simulate tool failure", source="chaos")

    def _inject_latency(self) -> None:
        """Inject latency jitter in loop submission cadence."""
        self._fault_injections["latency_injections"] += 1
        time.sleep(self._rng.uniform(0.005, 0.03))

    def _simulate_memory_corruption(self) -> None:
        """
        Simulate memory corruption logically (contract-safe).
        We inject malformed context requests/events and validate explicit handling.
        """
        self._fault_injections["memory_corruption_simulations"] += 1
        self._controller.submit_text("", source="chaos")
    
    def _collect_metrics(self) -> Dict:
        """Collect current system metrics including resilience observations."""
        execution_tracker = getattr(self._controller, "_execution_tracker", None)
        decision_engine = getattr(self._controller, "_decision_engine", None)
        resilience_observer = getattr(self._controller, "_resilience_observer", None)
        return {
            "timestamp": time.time(),
            "queue_depth": self._controller._event_queue.qsize(),
            "system_state": self._controller._system_state.name,
            "execution_stats": (
                execution_tracker.get_overall_stats() if execution_tracker else {"failure_rate": 0.0, "total_executions": 0}
            ),
            "decision_counts": decision_engine.get_decision_counts() if decision_engine else {},
            "resilience_metrics": resilience_observer.get_metrics() if resilience_observer else {}
        }
    
    def _analyze_behavior(self) -> Dict:
        """Analyze system behavior over test duration."""
        if not self._metrics_history:
            return {"error": "No metrics collected"}
        
        # Calculate statistics
        queue_depths = [m["queue_depth"] for m in self._metrics_history]
        failure_rates = [m["execution_stats"]["failure_rate"] for m in self._metrics_history]
        
        return {
            "max_queue_depth": max(queue_depths),
            "avg_queue_depth": sum(queue_depths) / len(queue_depths),
            "max_failure_rate": max(failure_rates),
            "avg_failure_rate": sum(failure_rates) / len(failure_rates),
            "state_transitions": len(set(m["system_state"] for m in self._metrics_history)),
            "final_state": self._metrics_history[-1]["system_state"]
        }
    
    def stop(self) -> None:
        """Stop the destructive test."""
        self._running = False
