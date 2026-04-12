"""Test SOKOL EVENT PIPELINE V2 implementation."""

import queue
import time
import threading

from sokol.runtime.backpressure import BackpressureLayer
from sokol.runtime.priority import PriorityPolicy, EventPriority
from sokol.runtime.metrics import MetricsCollector
from sokol.runtime.health import HealthChecker


def test_backpressure_layer():
    """Test backpressure layer functionality."""
    print("Testing BackpressureLayer...")
    
    # Create a test queue
    test_queue = queue.Queue(maxsize=10)
    backpressure = BackpressureLayer(test_queue, maxsize=10)
    
    # Test pressure levels
    assert backpressure.get_pressure_level() == "low", "Empty queue should be low pressure"
    
    # Fill queue to 20% (low pressure)
    for _ in range(2):
        test_queue.put(None)
    assert backpressure.get_pressure_level() == "low", "20% full should be low pressure"
    
    # Fill to 60%
    for _ in range(3):
        test_queue.put(None)
    assert backpressure.get_pressure_level() == "medium", "60% full should be medium pressure"
    
    # Fill to 80%
    for _ in range(2):
        test_queue.put(None)
    assert backpressure.get_pressure_level() == "high", "80% full should be high pressure"
    
    # Fill to 90%
    for _ in range(1):
        test_queue.put(None)
    assert backpressure.get_pressure_level() == "critical", "90% full should be critical pressure"
    
    # Test admission control
    accept, reason = backpressure.should_accept_event(event_priority=0)
    assert accept == True, "Emergency events should always be accepted"
    assert reason == "emergency_priority"
    
    accept, reason = backpressure.should_accept_event(event_priority=2)
    assert accept == False, "Low priority events should be rejected under critical pressure"
    assert reason == "queue_critical_pressure"
    
    # Test throttle delays
    delay = backpressure.get_throttle_delay_ms("user")
    assert delay > 0, "Critical pressure should have throttle delay"
    
    print("✓ BackpressureLayer tests passed")


def test_priority_policy():
    """Test priority policy functionality."""
    print("Testing PriorityPolicy...")
    
    policy = PriorityPolicy()
    
    # Test STOP event
    priority = policy.assign_priority("stop")
    assert priority == EventPriority.EMERGENCY.value, "STOP should be emergency priority"
    
    # Test TEXT_INPUT with confirmation
    priority = policy.assign_priority("text_input", data={"text": "да"})
    assert priority == EventPriority.EMERGENCY.value, "Confirmation should be emergency priority"
    
    # Test normal TEXT_INPUT
    priority = policy.assign_priority("text_input", data={"text": "hello"})
    assert priority == EventPriority.USER_INPUT.value, "Normal text should be user input priority"
    
    # Test VOICE_INPUT
    priority = policy.assign_priority("voice_input")
    assert priority == EventPriority.VOICE_INPUT.value, "Voice should be voice input priority"
    
    # Test SCREEN_CAPTURE
    priority = policy.assign_priority("screen_capture")
    assert priority == EventPriority.SCREEN_CAPTURE.value, "Screen should be screen capture priority"
    
    # Test drop policy
    should_drop, reason = policy.should_drop_under_pressure(
        EventPriority.EMERGENCY.value, "critical"
    )
    assert should_drop == False, "Emergency should never be dropped"
    
    should_drop, reason = policy.should_drop_under_pressure(
        EventPriority.BACKGROUND.value, "medium"
    )
    assert should_drop == True, "Background should be dropped under medium pressure"
    
    should_drop, reason = policy.should_drop_under_pressure(
        EventPriority.SCREEN_CAPTURE.value, "high"
    )
    assert should_drop == True, "Screen capture should be dropped under high pressure"
    
    print("✓ PriorityPolicy tests passed")


def test_metrics_collector():
    """Test metrics collector functionality."""
    print("Testing MetricsCollector...")
    
    metrics = MetricsCollector(max_history=100)
    
    # Test counter without tags
    metrics.increment_counter("test_counter", 1.0)
    metrics.increment_counter("test_counter", 2.0)
    
    all_metrics = metrics.get_all_metrics()
    assert "test_counter" in all_metrics["counters"]
    assert all_metrics["counters"]["test_counter"] == 3.0
    
    # Test gauge
    metrics.set_gauge("test_gauge", 42.0)
    all_metrics = metrics.get_all_metrics()
    assert "test_gauge" in all_metrics["gauges"]
    assert all_metrics["gauges"]["test_gauge"] == 42.0
    
    # Test histogram
    for i in range(10):
        metrics.observe_histogram("test_histogram", i * 10)
    
    stats = metrics.get_histogram_stats("test_histogram")
    assert stats["count"] == 10
    assert stats["min"] == 0
    assert stats["max"] == 90
    
    # Test Prometheus export
    prometheus = metrics.export_prometheus()
    assert "test_counter" in prometheus
    assert "test_gauge" in prometheus
    assert "test_histogram" in prometheus
    
    print("✓ MetricsCollector tests passed")


def test_health_checker():
    """Test health checker functionality."""
    print("Testing HealthChecker...")
    
    health = HealthChecker()
    
    # Register a passing check
    health.register_check("test_pass", lambda: True)
    
    # Register a failing check
    health.register_check("test_fail", lambda: False)
    
    status = health.get_health_status()
    assert status["status"] == "unhealthy"
    assert "test_pass" in status["checks"]
    assert "test_fail" in status["checks"]
    assert status["checks"]["test_pass"]["healthy"] == True
    assert status["checks"]["test_fail"]["healthy"] == False
    
    # Unregister failing check
    health.unregister_check("test_fail")
    
    status = health.get_health_status()
    assert status["status"] == "healthy"
    
    print("✓ HealthChecker tests passed")


def test_load_scenario_burst():
    """Test burst load scenario."""
    print("Testing burst load scenario...")
    
    test_queue = queue.Queue(maxsize=10)
    backpressure = BackpressureLayer(test_queue, maxsize=10)
    policy = PriorityPolicy()
    metrics = MetricsCollector()
    
    # Simulate burst of 20 events (more than queue capacity)
    events_submitted = 0
    events_dropped = 0
    
    for i in range(20):
        priority = policy.assign_priority("text_input", data={"text": f"test_{i}"})
        pressure = backpressure.get_pressure_level()
        
        should_drop, drop_reason = policy.should_drop_under_pressure(priority, pressure)
        if should_drop:
            events_dropped += 1
            metrics.increment_counter("events_dropped_total", tags={"reason": drop_reason})
            continue
        
        accept, accept_reason = backpressure.should_accept_event(priority)
        if not accept:
            events_dropped += 1
            metrics.increment_counter("events_throttled_total", tags={"reason": accept_reason})
            continue
        
        try:
            test_queue.put_nowait(f"test_{i}")
            events_submitted += 1
            metrics.increment_counter("events_submitted_total")
        except queue.Full:
            events_dropped += 1
            metrics.increment_counter("events_dropped_total", tags={"reason": "queue_full"})
    
    all_metrics = metrics.get_all_metrics()
    print(f"  Events submitted: {events_submitted}")
    print(f"  Events dropped: {events_dropped}")
    print(f"  Queue depth: {test_queue.qsize()}")
    
    assert events_submitted == 10, "Should submit exactly queue capacity"
    assert events_dropped == 10, "Should drop remaining events"
    
    print("✓ Burst load scenario test passed")


def test_load_scenario_priority():
    """Test priority-based event handling under pressure."""
    print("Testing priority-based event handling...")
    
    test_queue = queue.Queue(maxsize=5)
    backpressure = BackpressureLayer(test_queue, maxsize=5)
    policy = PriorityPolicy()
    
    # Fill queue to high pressure
    for _ in range(4):
        test_queue.put(None)
    
    # Try to submit different priority events
    # Emergency should always be accepted
    priority = policy.assign_priority("stop")
    accept, reason = backpressure.should_accept_event(priority)
    assert accept == True, "Emergency should be accepted"
    
    # Screen capture might be dropped under pressure
    priority = policy.assign_priority("screen_capture")
    should_drop, drop_reason = policy.should_drop_under_pressure(priority, "high")
    assert should_drop == True, "Screen capture should be dropped under high pressure"
    
    print("✓ Priority-based event handling test passed")


def run_all_tests():
    """Run all V2 pipeline tests."""
    print("\n" + "="*60)
    print("SOKOL EVENT PIPELINE V2 - TEST SUITE")
    print("="*60 + "\n")
    
    test_backpressure_layer()
    test_priority_policy()
    test_metrics_collector()
    test_health_checker()
    test_load_scenario_burst()
    test_load_scenario_priority()
    
    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
