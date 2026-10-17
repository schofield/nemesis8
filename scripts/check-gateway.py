#!/usr/bin/env python3
"""Probe host services from the same network namespace as an agent."""
import http.client
import socket
import sys


def check_gateway(host, gateway_port, tunnel_port):
    failures = []
    connection = http.client.HTTPConnection(host, gateway_port, timeout=3)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        if response.status != 200:
            raise OSError(f"HTTP {response.status}")
        print(f"gateway {host}:{gateway_port}: OK", flush=True)
    except (OSError, http.client.HTTPException) as error:
        failures.append(f"gateway {host}:{gateway_port}: {error}")
    finally:
        connection.close()
    try:
        with socket.create_connection((host, tunnel_port), timeout=3):
            print(f"reverse tunnel {host}:{tunnel_port}: OK", flush=True)
    except OSError as error:
        failures.append(f"reverse tunnel {host}:{tunnel_port}: {error}")
    for failure in failures:
        print(failure, file=sys.stderr, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(check_gateway(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
