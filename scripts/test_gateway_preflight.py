"""Exercise the setup probe with real local HTTP and TCP listeners."""
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest

PROBE = Path(__file__).with_name("check-gateway.py")


class GatewayPreflightTests(unittest.TestCase):
    def setUp(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if self.path == "/health" else 404)
                self.end_headers()
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)

    def probe(self, gateway, tunnel):
        return subprocess.run(
            [sys.executable, str(PROBE), "127.0.0.1", str(gateway), str(tunnel)],
            capture_output=True, text=True, timeout=10,
        )

    def test_gateway_and_tunnel_are_both_reachable(self):
        with contextlib.closing(socket.socket()) as tunnel:
            tunnel.bind(("127.0.0.1", 0))
            tunnel.listen()
            result = self.probe(self.server.server_port, tunnel.getsockname()[1])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gateway 127.0.0.1:", result.stdout)
        self.assertIn("reverse tunnel 127.0.0.1:", result.stdout)

    def test_host_health_alone_does_not_hide_unreachable_tunnel(self):
        # Reserve a port without listening, so another test cannot take it.
        with contextlib.closing(socket.socket()) as closed:
            closed.bind(("127.0.0.1", 0))
            result = self.probe(self.server.server_port, closed.getsockname()[1])
        self.assertEqual(result.returncode, 1)
        self.assertIn("gateway 127.0.0.1:", result.stdout)
        self.assertIn("reverse tunnel 127.0.0.1:", result.stderr)

    def test_gateway_failure_is_reported_even_if_tunnel_is_reachable(self):
        with contextlib.closing(socket.socket()) as closed, contextlib.closing(socket.socket()) as tunnel:
            closed.bind(("127.0.0.1", 0))
            tunnel.bind(("127.0.0.1", 0))
            tunnel.listen()
            result = self.probe(closed.getsockname()[1], tunnel.getsockname()[1])
        self.assertEqual(result.returncode, 1)
        self.assertIn("gateway 127.0.0.1:", result.stderr)
        self.assertIn("reverse tunnel 127.0.0.1:", result.stdout)


if __name__ == "__main__":
    unittest.main()
