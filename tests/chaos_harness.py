"""Continuous chaos runner for Validation & Hardening."""

import time
import random
from typing import Dict, List


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
    
    def __init__(self, live_loop_controller):
        """
        Initialize continuous chaos runner.
        
        Args:
            live_loop_controller: LiveLoopController instance to stress
        """
        self._controller = live_loop_controller
        self._running = False
        self._metrics_history = []
    
    def run_destructive_test(self, duration_hours: int = 6) -> Dict[str, any]:
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
        
        while time.time() < end_time and self._running:
            # Random chaos: burst events
            if random.random() < 0.1:  # 10% chance of burst
                self._inject_burst()
            
            # Random chaos: emergency during stress
            if random.random() < 0.01:  # 1% chance of emergency
                self._inject_emergency()
            
            # Continuous load: normal events
            self._controller.submit_text(f"chaos test {int(time.time())}")
            
            # Collect metrics every 30 seconds
            if int(time.time()) % 30 == 0:
                metrics = self._collect_metrics()
                self._metrics_history.append(metrics)
                print(f"Metrics collected: {metrics}")
            
            # Random sleep (50-500ms)
            time.sleep(random.uniform(0.05, 0.5))
        
        duration = time.time() - start_time
        
        return {
            "test_name": f"continuous_chaos_{duration_hours}h",
            "status": "completed" if self._running else "interrupted",
            "duration_seconds": duration,
            "metrics_history": self._metrics_history,
            "observations": self._analyze_behavior()
        }
    
    def _inject_burst(self) -> None:
        """Inject burst of events."""
        burst_size = random.randint(10, 50)
        for i in range(burst_size):
            self._controller.submit_text(f"burst event {i}")
            time.sleep(0.01)  # 10ms between events
        print(f"Burst injected: {burst_size} events")
    
    def _inject_emergency(self) -> None:
        """Inject emergency event during stress."""
        emergency_commands = ["stop", "emergency", "abort"]
        cmd = random.choice(emergency_commands)
        self._controller.submit_text(cmd)
        print(f"Emergency injected: {cmd}")
    
    def _collect_metrics(self) -> Dict:
        """Collect current system metrics including resilience observations."""
        return {
            "timestamp": time.time(),
            "queue_depth": self._controller._event_queue.qsize(),
            "system_state": self._controller._system_state.name,
            "execution_stats": self._controller._execution_tracker.get_overall_stats(),
            "decision_counts": self._controller._decision_engine.get_decision_counts(),
            "resilience_metrics": self._controller._resilience_observer.get_metrics()
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
