"""Ladecockpit starten: `python -m app`.

Bei SIGTERM fährt uvicorn die App sauber herunter und löst das Signal danach erneut aus, sodass
der Prozess mit Exit-Code 143 endet. Home Assistant hält das für eine App, die SIGTERM nicht
behandelt hat. Nach dem sauberen Herunterfahren endet Ladecockpit stattdessen mit Exit-Code 0.
"""

import signal
import sys

import uvicorn


def _stopped(_signum, _frame) -> None:
    sys.exit(0)


def main(port: int = 8077) -> None:
    # uvicorn setzt während des Laufs einen eigenen Handler ein und stellt diesen danach wieder her.
    signal.signal(signal.SIGTERM, _stopped)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, proxy_headers=True)


if __name__ == "__main__":
    main()
