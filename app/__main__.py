"""Start Ladecockpit: `python -m app`.

On SIGTERM uvicorn shuts the app down cleanly, then raises the signal again so the
process ends with exit code 143. Home Assistant takes that for an app that did not
handle SIGTERM. After the clean shutdown, Ladecockpit ends with exit code 0 instead.
"""

import signal
import sys

import uvicorn


def _stopped(_signum, _frame) -> None:
    sys.exit(0)


def main(port: int = 8077) -> None:
    # uvicorn swaps in its own handler while it runs and puts this one back afterwards.
    signal.signal(signal.SIGTERM, _stopped)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, proxy_headers=True)


if __name__ == "__main__":
    main()
