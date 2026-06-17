import subprocess, json, http.server, urllib.request, os, time, gzip, threading
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass
from collections import deque
from datetime import datetime, timezone

PORT = 8063
HTML_FILE = os.path.join(os.path.dirname(__file__), "llama-dashboard.html")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

LLAMA_URL = "http://192.168.1.205:8083"
API_KEY = "lazailai"

RPC_HOST = os.environ.get("RPC_SSH_HOST", "")
RPC_USER = os.environ.get("RPC_SSH_USER", "")
RPC_PASS = os.environ.get("RPC_SSH_PASS", "")

os.makedirs(DATA_DIR, exist_ok=True)

HOUR_SECONDS = 3600
STORE_MAX = 7200

GPU_FIELDS = [
    "index", "name", "temperature.gpu", "utilization.gpu", "utilization.memory",
    "memory.total", "memory.used", "memory.free", "power.draw",
    "clocks.current.graphics", "clocks.current.memory", "fan.speed",
    "pcie.link.gen.current", "pcie.link.width.current"
]

store = deque()
store_lock = threading.Lock()

def parse_smi_output(text):
    gpus = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == len(GPU_FIELDS):
            gpu = dict(zip(GPU_FIELDS, parts))
            for k in ["temperature.gpu", "utilization.gpu", "utilization.memory",
                      "memory.total", "memory.used", "memory.free", "power.draw",
                      "clocks.current.graphics", "clocks.current.memory",
                      "fan.speed", "pcie.link.gen.current", "pcie.link.width.current"]:
                try:
                    gpu[k] = float(gpu[k]) if "." in str(gpu[k]) else int(gpu[k])
                except ValueError:
                    gpu[k] = 0
            gpus.append(gpu)
    return gpus

def run_nvidia_smi_local():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=" + ",".join(GPU_FIELDS), "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if out.returncode != 0:
            return []
        return parse_smi_output(out.stdout)
    except Exception:
        return []

def run_nvidia_smi_remote():
    if not RPC_HOST or not RPC_USER or not RPC_PASS:
        return []
    try:
        cmd = [
            "sshpass", "-p", RPC_PASS,
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=3",
            f"{RPC_USER}@{RPC_HOST}",
            "nvidia-smi --query-gpu=" + ",".join(GPU_FIELDS) + " --format=csv,noheader,nounits"
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return []
        return parse_smi_output(out.stdout)
    except Exception:
        return []

NET_IFACES_LOCAL = ["enp5s0", "wlp6s0"]
NET_IFACES_REMOTE = ["enp6s0", "wlan0"]

def read_net_dev(text, ifaces):
    result = {}
    for line in text.split("\n"):
        parts = line.split(":")
        if len(parts) != 2:
            continue
        name = parts[0].strip()
        if name not in ifaces:
            continue
        vals = parts[1].split()
        if len(vals) >= 9:
            result[name] = {"rx_bytes": int(vals[0]), "tx_bytes": int(vals[8])}
    return result

def get_net_local():
    try:
        with open("/proc/net/dev") as f:
            return read_net_dev(f.read(), NET_IFACES_LOCAL)
    except Exception:
        return {}

def get_net_remote():
    if not RPC_HOST or not RPC_USER or not RPC_PASS:
        return {}
    try:
        cmd = ["sshpass", "-p", RPC_PASS, "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=3", f"{RPC_USER}@{RPC_HOST}", "cat /proc/net/dev"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return {}
        return read_net_dev(out.stdout, NET_IFACES_REMOTE)
    except Exception:
        return {}

def fetch_url(path):
    try:
        req = urllib.request.Request(f"{LLAMA_URL}{path}", headers={"Authorization": f"Bearer {API_KEY}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode()
    except Exception:
        return None

def parse_metrics(text):
    m = {}
    for line in text.split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0].replace("llamacpp:", "")
            try:
                m[key] = float(parts[1])
            except ValueError:
                m[key] = parts[1]
    return m

_prev_net_local = {}
_prev_net_remote = {}
_prev_net_ts = 0

def collect_snapshot():
    global _prev_net_local, _prev_net_remote, _prev_net_ts
    metrics_text = fetch_url("/metrics")
    slots_text = fetch_url("/slots")
    local_gpus = run_nvidia_smi_local()
    remote_gpus = run_nvidia_smi_remote()
    now = time.time()
    snap = {
        "ts": now,
        "gpus_local": local_gpus,
        "gpus_remote": remote_gpus,
    }
    net_local = get_net_local()
    net_remote = get_net_remote()
    dt = now - _prev_net_ts if _prev_net_ts > 0 else 1
    snap["net_local"] = {"ifaces": {}}
    for name, val in net_local.items():
        prev = _prev_net_local.get(name, {})
        rx = val["rx_bytes"]
        tx = val["tx_bytes"]
        snap["net_local"]["ifaces"][name] = {
            "rx_bytes": rx, "tx_bytes": tx,
            "rx_kBs": round((rx - prev.get("rx_bytes", rx)) / dt / 1024, 1) if _prev_net_ts > 0 else 0,
            "tx_kBs": round((tx - prev.get("tx_bytes", tx)) / dt / 1024, 1) if _prev_net_ts > 0 else 0,
        }
    _prev_net_local = net_local

    snap["net_remote"] = {"ifaces": {}}
    for name, val in net_remote.items():
        prev = _prev_net_remote.get(name, {})
        rx = val["rx_bytes"]
        tx = val["tx_bytes"]
        snap["net_remote"]["ifaces"][name] = {
            "rx_bytes": rx, "tx_bytes": tx,
            "rx_kBs": round((rx - prev.get("rx_bytes", rx)) / dt / 1024, 1) if _prev_net_ts > 0 else 0,
            "tx_kBs": round((tx - prev.get("tx_bytes", tx)) / dt / 1024, 1) if _prev_net_ts > 0 else 0,
        }
    _prev_net_remote = net_remote
    _prev_net_ts = now

    if metrics_text:
        snap["metrics_raw"] = metrics_text
        snap["metrics"] = parse_metrics(metrics_text)
    if slots_text:
        try:
            snap["slots"] = json.loads(slots_text)
        except json.JSONDecodeError:
            snap["slots"] = []
    return snap

def archive_hour(entries):
    if not entries:
        return
    dt = datetime.fromtimestamp(entries[0]["ts"], tz=timezone.utc)
    fname = f"{DATA_DIR}/{dt.strftime('%Y-%m-%dT%H')}.json.gz"
    try:
        with gzip.open(fname, "wt", encoding="utf-8") as f:
            json.dump(entries, f, separators=(",", ":"))
    except Exception:
        pass

def prune_and_archive():
    global store
    now = time.time()
    cutoff = now - HOUR_SECONDS
    with store_lock:
        old = [s for s in store if s["ts"] < cutoff]
        store = deque([s for s in store if s["ts"] >= cutoff], maxlen=STORE_MAX)
    if old:
        archive_hour(old)

def collector_loop():
    while True:
        try:
            snap = collect_snapshot()
            with store_lock:
                store.append(snap)
            prune_and_archive()
        except Exception:
            pass
        time.sleep(1)

def load_archive_files(since_ts):
    results = []
    try:
        for fname in sorted(os.listdir(DATA_DIR)):
            if not fname.endswith(".json.gz"):
                continue
            with gzip.open(os.path.join(DATA_DIR, fname), "rt", encoding="utf-8") as f:
                entries = json.load(f)
            results.extend(e for e in entries if e["ts"] >= since_ts)
    except Exception:
        pass
    return results

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/all":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            snap = collect_snapshot()
            self.wfile.write(json.dumps(snap).encode())

        elif self.path == "/api/history":
            since = time.time() - 7200
            qs = self.path.split("?", 1)
            if len(qs) > 1:
                for part in qs[1].split("&"):
                    if part.startswith("since="):
                        try:
                            since = float(part[6:])
                        except ValueError:
                            pass
            archived = load_archive_files(since)
            with store_lock:
                recent = [s for s in store if s["ts"] >= since]
            merged = archived + recent
            merged.sort(key=lambda x: x["ts"])
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            payload = json.dumps(merged, separators=(",", ":")).encode()
            self.wfile.write(gzip.compress(payload))

        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            try:
                with open(HTML_FILE) as f:
                    self.wfile.write(f.read().encode())
            except FileNotFoundError:
                self.wfile.write(b"<h1>llama-dashboard.html not found</h1>")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    t = threading.Thread(target=collector_loop, daemon=True)
    t.start()
    srv = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Dashboard server on http://0.0.0.0:{PORT}")
    print(f"Data dir: {DATA_DIR}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
