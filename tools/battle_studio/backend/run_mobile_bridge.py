from __future__ import annotations

import argparse
import socket
from pathlib import Path

import uvicorn


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            value = info[4][0]
            if value and not value.startswith("127."):
                addresses.add(value)
    except socket.gaierror:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            value = probe.getsockname()[0]
            if value and not value.startswith("127."):
                addresses.add(value)
    except OSError:
        pass
    return sorted(addresses)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve BLACK Battle Studio to iPhone on the local network.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    print("BLACK Battle Studio mobile bridge")
    print(f"Backend root: {root}")
    print("Open one of these URLs on the iPhone connected to the same Wi-Fi:")
    addresses = local_ipv4_addresses()
    if addresses:
        for address in addresses:
            print(f"  http://{address}:{args.port}/")
    else:
        print(f"  http://<PC-LAN-IP>:{args.port}/")
    print("The official engine remains on WSL2; the iPhone is only the control/display client.")

    uvicorn.run("live_server:app", host=args.host, port=args.port, app_dir=str(root), log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
