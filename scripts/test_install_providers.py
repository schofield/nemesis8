"""Exercise installer downloads against a local HTTP failure server."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location(
    "install_providers", Path(__file__).with_name("install-providers.py")
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@unittest.skipUnless(shutil.which("curl") and shutil.which("bash"), "requires curl and bash")
class InstallerDownloadTests(unittest.TestCase):
    def run_server(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}/install.sh"

    def test_rate_limit_retries_without_executing_error_body(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "executions"
            class Handler(BaseHTTPRequestHandler):
                requests = 0
                def do_GET(self):
                    Handler.requests += 1
                    self.send_response(429 if Handler.requests == 1 else 200)
                    self.send_header("Retry-After", "0")
                    self.end_headers()
                    if Handler.requests == 1:
                        self.wfile.write(b'echo ERROR_BODY_EXECUTED >> "$1"\n')
                    else:
                        self.wfile.write(b'printf "%s\\n" "$2" >> "$1"\n')
                def log_message(self, *args):
                    pass
            url = self.run_server(Handler)
            installer.run_curl_installer(url, [str(marker), "argument with spaces; $literal"])
            self.assertEqual(Handler.requests, 2)
            self.assertEqual(marker.read_text(), "argument with spaces; $literal\n")

    def test_failed_download_never_executes_script(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "executions"
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'echo SHOULD_NOT_RUN >> "$1"\n')
                def log_message(self, *args):
                    pass
            with self.assertRaises(subprocess.CalledProcessError):
                installer.run_curl_installer(self.run_server(Handler), [str(marker)])
            self.assertFalse(marker.exists())

    def test_partial_download_is_discarded(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "executions"
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header("Content-Length", "10000")
                    self.end_headers()
                    self.wfile.write(b'echo PARTIAL_SCRIPT >> "$1"\n')
                    self.close_connection = True
                def log_message(self, *args):
                    pass
            with self.assertRaises(subprocess.CalledProcessError):
                installer.run_curl_installer(self.run_server(Handler), [str(marker)])
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
