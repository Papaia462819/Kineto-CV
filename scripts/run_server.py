"""Pornește serverul Kineto-CV în rețeaua locală, ca telefonul să-l poată folosi.

Rulare:
    python scripts/run_server.py              # portul 8000
    python scripts/run_server.py --port 8080

Telefonul și laptopul trebuie să fie în aceeași rețea Wi-Fi. Adresa de pus în aplicație e afișată la pornire.
Prima dată, Windows poate întreba dacă Python are voie în rețea: alege „Rețele private”.
"""
import argparse
import socket
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.api import create_app


def lan_address():
    """Adresa laptopului în rețeaua locală (nu trimite nimic: doar alege interfața spre o adresă externă)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"In aplicatie, la Setari, pune adresa: http://{lan_address()}:{args.port}")
    print(f"Verificare din browser: http://{lan_address()}:{args.port}/api/health   (documentatie: /docs)")
    # 0.0.0.0 = ascultă pe toate interfețele, nu doar pe laptop, ca să-l vadă telefonul.
    uvicorn.run(create_app(), host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
