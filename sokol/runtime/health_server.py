"""HTTP health check server for production observability."""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check and metrics endpoints."""
    
    def __init__(self, health_checker, metrics_collector, *args, **kwargs):
        """
        Initialize handler with dependencies.
        
        Args:
            health_checker: HealthChecker instance
            metrics_collector: MetricsCollector instance
        """
        self.health_checker = health_checker
        self.metrics_collector = metrics_collector
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/metrics":
            self._handle_metrics()
        elif self.path == "/":
            self._handle_root()
        else:
            self._handle_not_found()
    
    def _handle_root(self):
        """Handle root endpoint with basic info."""
        response = {
            "service": "SOKOL Agent",
            "version": "2.0",
            "endpoints": {
                "/health": "Health check status",
                "/metrics": "Prometheus metrics"
            }
        }
        self._send_json_response(200, response)
    
    def _handle_health(self):
        """Handle health check endpoint."""
        try:
            status = self.health_checker.get_health_status()
            http_code = 200 if status["status"] == "healthy" else 503
            self._send_json_response(http_code, status)
        except Exception as e:
            self._send_json_response(500, {"error": str(e)})
    
    def _handle_metrics(self):
        """Handle metrics endpoint (Prometheus format)."""
        try:
            metrics = self.metrics_collector.export_prometheus()
            self._send_text_response(200, metrics, "text/plain")
        except Exception as e:
            self._send_json_response(500, {"error": str(e)})
    
    def _handle_not_found(self):
        """Handle 404."""
        self._send_json_response(404, {"error": "Not found"})
    
    def _send_json_response(self, code: int, data: dict):
        """Send JSON response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def _send_text_response(self, code: int, text: str, content_type: str):
        """Send text response."""
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(text.encode())
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class HealthCheckServer:
    """
    HTTP server for health checks and metrics.
    
    Provides:
    - /health endpoint
    - /metrics endpoint (Prometheus format)
    - Runs in background thread
    """
    
    def __init__(self, health_checker, metrics_collector, host: str = "127.0.0.1", port: int = 8080):
        """
        Initialize health check server.
        
        Args:
            health_checker: HealthChecker instance
            metrics_collector: MetricsCollector instance
            host: Host to bind to
            port: Port to bind to
        """
        self.health_checker = health_checker
        self.metrics_collector = metrics_collector
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> bool:
        """
        Start the health check server.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            return False
        
        try:
            # Create handler with dependencies
            def handler(*args, **kwargs):
                return HealthCheckHandler(
                    self.health_checker,
                    self.metrics_collector,
                    *args,
                    **kwargs
                )
            
            self._server = HTTPServer((self.host, self.port), handler)
            self._running = True
            
            # Start server in background thread
            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="HealthCheckServer"
            )
            self._server_thread.start()
            
            return True
        except Exception as e:
            print(f"Failed to start health check server: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the health check server."""
        if not self._running:
            return
        
        self._running = False
        if self._server:
            self._server.shutdown()
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=2.0)
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
