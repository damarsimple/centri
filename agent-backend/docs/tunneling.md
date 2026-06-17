# Proxy Tunnels: lab1 (public IP) → internal services

## Topology

```
Internet ──→ 140.115.126.111 (lab1)
                  │
        ┌─────────┼─────────┐
        │ 8082          8084 │
     socat-proxy    socat-llama
        │               │
  10.0.0.2:8000   192.168.1.205:8083
   (lab2 API)      (llama-server)
```

- **lab1** — PC with public IP `140.115.126.111` on `enp116s0u1`, LAN IP `10.0.0.1`
- **lab2** — PC running the FastAPI docker container on port `8000`, LAN IP `10.0.0.2`
- **llama-server** — inference server at `192.168.1.205:8083` (on WiFi network, reachable from lab1 via wlan0)
- Direct LAN connection between lab1 and lab2 via ethernet on `10.0.0.0/24`

---

## Tunnel 1: Agent Backend API (port 8082)

Forwards `lab1:8082` → `lab2:8000` (agent-backend API container).

### Access
- **Anyone** with the API key can access (port open to all inbound).
- URL: `http://140.115.126.111:8082/`

### Service

```ini
# /etc/systemd/system/socat-proxy.service
[Unit]
Description=Socat proxy 8082 -> 10.0.0.2:8000
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/socat TCP-LISTEN:8082,fork,reuseaddr TCP:10.0.0.2:8000
Restart=always
RestartSec=5
User=damar

[Install]
WantedBy=multi-user.target
```

---

## Tunnel 2: llama-server Inference (port 8084)

Forwards `lab1:8084` → `192.168.1.205:8083` (llama.cpp inference server).

### Access — IP-restricted
| Source | Permission |
|---|---|
| `10.0.0.2` (lab2, this PC) | ✅ Allow |
| `140.115.126.108` (labmate) | ✅ Allow |
| All others | ❌ Deny |

URL: `http://140.115.126.111:8084/`

### Service

```ini
# /etc/systemd/system/socat-llama.service
[Unit]
Description=Socat proxy 8084 -> 192.168.1.205:8083 (llama-server)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/socat TCP-LISTEN:8084,fork,reuseaddr TCP:192.168.1.205:8083
Restart=always
RestartSec=5
User=damar

[Install]
WantedBy=multi-user.target
```

### UFW Rules

```bash
sudo ufw allow from 10.0.0.2 to any port 8084 proto tcp
sudo ufw allow from 140.115.126.108 to any port 8084 proto tcp
sudo ufw deny 8084/tcp   # blanket deny after the specific allows
```

Rules are processed in order: specific allows match first, blanket deny catches everything else.

---

## Common Commands

```bash
# Status
sudo systemctl status socat-proxy.service
sudo systemctl status socat-llama.service

# Restart
sudo systemctl restart socat-proxy.service
sudo systemctl restart socat-llama.service

# Logs
sudo journalctl -u socat-proxy.service -f
sudo journalctl -u socat-llama.service -f
```

## Upstream Router

Gateway `140.115.126.254` may block inbound connections. If external access fails, the router needs port forwarding — nothing on lab1 blocks traffic beyond UFW.

## Tailscale Alternative

Both lab PCs are on the same tailnet:

| PC | Tailscale IP |
|---|---|
| lab1 | `100.73.83.98` |
| lab2 | `100.82.113.90` |

For direct access without relying on public IP:

```bash
tailscale funnel 8082
tailscale funnel 8084
```

Creates public HTTPS URLs via Tailscale's edge, bypassing the upstream router.

## How to Verify

From lab2 (10.0.0.2):

```bash
# API tunnel
curl -H "X-API-Key: changeme-random-secret-key-12345" http://140.115.126.111:8082/

# llama-server tunnel (expected: 404 or valid response from llama)
curl http://140.115.126.111:8084/
```

From external: same commands against the public IP.
