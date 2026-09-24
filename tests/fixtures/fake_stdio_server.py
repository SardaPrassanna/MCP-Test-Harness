"""Entry point that runs the fake MCP test server over stdio.

Launched only as a subprocess by the stdio connection/discovery tests;
never imported directly. It lives next to `fake_server.py` (rather than in
the `tests` package) so it can `import fake_server` from its own directory
when Python runs it as a standalone script.
"""

import argparse
import time

from fake_server import build_fake_server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--startup-delay", type=float, default=0.0)
    args = parser.parse_args()

    if args.startup_delay:
        time.sleep(args.startup_delay)

    build_fake_server().run(transport="stdio")


if __name__ == "__main__":
    main()
