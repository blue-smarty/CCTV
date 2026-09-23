# CCTV

Minimal Python CLI to interact with home CCTV systems, especially Swann cameras/NVRs.

## Usage

```bash
read -s CCTV_PASSWORD && export CCTV_PASSWORD
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" snapshot-url --channel 1
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" status
python cctv.py --host 192.168.1.20 --username admin --password "$CCTV_PASSWORD" request --path /api/status
```

Use `--https` and `--port` if your Swann device is configured for HTTPS or a custom port.
