# CCTV

Minimal Python CLI to interact with home CCTV systems, especially Swann cameras/NVRs.

## How to use

### Prerequisites

- Python 3.8 or newer
- A reachable Swann camera or NVR on your local network
- The device hostname or IP address, username, and password

### Quick start

Set the password as an environment variable so it is not echoed in your shell:

```bash
read -r -s -p "CCTV password: " CCTV_PASSWORD; echo; export CCTV_PASSWORD
```

Then run commands against your device:

```bash
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" snapshot-url --channel 1
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" status
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" request --path /api/status
```

Use `--https` and `--port` when your camera/NVR is configured for HTTPS or a custom port:

```bash
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" --https --port 443 status
```

### Common commands

The CLI supports these actions:

- `snapshot-url` - generate the URL for a camera snapshot
- `status` - fetch the device status endpoint
- `request` - send a raw HTTP request to a custom endpoint

Examples:

```bash
# Generate a snapshot URL for channel 2
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" snapshot-url --channel 2

# Fetch the default status page
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" status

# Call a custom endpoint
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" request --path /ISAPI/System/status --method GET --accept application/json
```

You can also pass the password directly instead of using an environment variable:

```bash
python cctv.py --host 192.168.1.20 --username admin --password "your-password" status
```

### Secure GUI

You can also run the secure GUI client:

```bash
python cctv_gui.py
```

The GUI includes fields for host, username, password, port, timeout, and HTTPS mode. It masks the password input and makes it easier to generate snapshot URLs, fetch status, and send custom requests.

### Notes

- `--https` is recommended for secure access.
- If your device uses a non-default port, pass `--port`.
- If your camera or NVR responds with a different status path, use `status --path` or `request --path` with the correct endpoint.
