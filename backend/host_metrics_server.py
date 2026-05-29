"""
J.A.R.V.I.S. — Host Metrics Server (Windows)

Run this OUTSIDE Docker to expose REAL Windows host metrics.
Usage:  python host_metrics_server.py
Endpoint: http://localhost:18765/api/system/metrics
         http://localhost:18765/api/system/logs
"""

import json
import http.server
import platform
import subprocess
import re
import time
from collections import deque
from datetime import datetime, timezone

import psutil

HOST = "0.0.0.0"
PORT = 18765

# ── Metric history (same format as Docker backend) ────────────────────────────
_metric_history = {
    "cpu": deque(maxlen=60),
    "ram": deque(maxlen=60),
    "temp": deque(maxlen=60),
    "disk": deque(maxlen=60),
}

_system_logs = deque(maxlen=100)
_system_logs.append({
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "level": "info",
    "message": f"Host Metrics Server avviato — {platform.system()} {platform.release()}",
})


def _get_temperature():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    return round(entries[0].current, 1)
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "/namespace:\\\\root\\wmi", "path", "MSAcpi_ThermalZoneTemperature", "get", "CurrentTemperature"],
                capture_output=True, text=True, timeout=5,
            )
            match = re.search(r"(\d+)", result.stdout)
            if match:
                kelvin = int(match.group(1))
                return round(kelvin / 10 - 273.15, 1)
    except Exception:
        pass
    return None


def _get_top_processes(limit=5):
    procs = []
    for p in sorted(
        psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
        key=lambda p: p.info.get("cpu_percent", 0) or 0,
        reverse=True,
    )[:limit]:
        try:
            procs.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "cpu": round(p.info["cpu_percent"] or 0, 1),
                "mem": round(p.info["memory_percent"] or 0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs


def _collect_metrics():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    temp = _get_temperature()
    procs = _get_top_processes()
    net = psutil.net_io_counters()

    metrics = {
        "cpu": round(cpu, 1),
        "ram": round(ram.percent, 1),
        "ram_gb": round(ram.used / (1024 ** 3), 1),
        "ram_total_gb": round(ram.total / (1024 ** 3), 1),
        "temp": temp,
        "disk": round(disk.percent, 1),
        "disk_gb": round(disk.used / (1024 ** 3), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
        "net_sent": round(net.bytes_sent / (1024 ** 2), 2),
        "net_recv": round(net.bytes_recv / (1024 ** 2), 2),
        "uptime": round(psutil.boot_time()),
        "processes": procs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "windows_host",
    }

    _metric_history["cpu"].append(metrics["cpu"])
    _metric_history["ram"].append(metrics["ram"])
    if temp is not None:
        _metric_history["temp"].append(temp)
    _metric_history["disk"].append(metrics["disk"])

    return {**metrics, "history": {k: list(v) for k, v in _metric_history.items()}}



def _update_logs():
    cpu = psutil.cpu_percent(interval=0)
    ram = psutil.virtual_memory()
    if cpu > 85:
        _system_logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "warning",
            "message": f"CPU criticamente alta: {cpu}%",
        })
    if ram.percent > 85:
        _system_logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "warning",
            "message": f"RAM criticamente alta: {ram.percent}%",
        })
    if cpu < 10 and _system_logs[-1]["level"] != "info":
        _system_logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "info",
            "message": f"Sistema in idle — CPU {cpu}%, RAM {ram.percent}%",
        })


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({})

    def do_GET(self):
        if self.path == "/api/system/metrics":
            metrics = _collect_metrics()
            self._send_json(metrics)
        elif self.path == "/api/system/logs":
            _update_logs()
            self._send_json({"logs": list(_system_logs)})
        else:
            self._send_json({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        pass  # quiet


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print("J.A.R.V.I.S. Host Metrics Server")
    print("-------")
    print(f"Server in esecuzione su http://{HOST}:{PORT}")
    print(f"Endpoint metriche: http://localhost:{PORT}/api/system/metrics")
    print(f"Endpoint logs:     http://localhost:{PORT}/api/system/logs")
    print("Premi Ctrl+C per fermarlo.")
    print()

    server = http.server.HTTPServer((HOST, PORT), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer fermato.")
        server.server_close()
