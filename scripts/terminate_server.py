#!/usr/bin/env python3
"""Utility script to terminate any process listening on a given TCP port.

Usage:
    python terminate_server.py <port>

Works on Windows (using `netstat -ano`) and Unix-like systems (using `lsof`).
It finds the PID(s) of processes bound to the specified port and kills them.
"""
import sys
import subprocess
import platform
import re

def kill_process(pid: str):
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", pid, "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["kill", "-9", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] Failed to kill PID {pid}: {e}")

def terminate_port(port: str):
    if not port.isdigit():
        print(f"[!] Invalid port: {port}")
        return
    port_num = int(port)
    system = platform.system()
    if system == "Windows":
        # netstat -ano lists all connections with PID
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        pattern = re.compile(r"\s*TCP\s+[^:]+:(\d+)\s+[^:]+:\d+\s+LISTENING\s+(\d+)")
        for line in lines:
            m = pattern.search(line)
            if m and int(m.group(1)) == port_num:
                kill_process(m.group(2))
    else:
        # Use lsof on Unix-like systems
        result = subprocess.run(["lsof", "-i", f"TCP:{port_num}"], capture_output=True, text=True)
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                pid = parts[1]
                kill_process(pid)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python terminate_server.py <port>")
        sys.exit(1)
    terminate_port(sys.argv[1])
