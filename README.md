# CCTV

Minimal Python CLI to interact with home CCTV systems, especially Swann cameras/NVRs.

## Usage

```bash
python cctv.py --host 192.168.1.20 --username admin --password secret snapshot-url --channel 1
python cctv.py --host 192.168.1.20 --username admin --password secret status
python cctv.py --host 192.168.1.20 --username admin --password secret request --path /api/status
```

Use `--https` and `--port` if your Swann device is configured for HTTPS or a custom port.
