"""Open a screenshot investigation from a portable input manifest."""

import argparse
import json
import time
import webbrowser

from beakdown_core.investigation import read_json

from .tools import create_investigation_session, manager


def main():
    parser = argparse.ArgumentParser(
        description="Open a Beakdown screenshot investigation"
    )
    parser.add_argument(
        "manifest",
        help="Absolute JSON manifest path; fields match create_investigation_session",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Print the URL without opening a browser"
    )
    args = parser.parse_args()
    result = create_investigation_session(**read_json(args.manifest))
    print(json.dumps(result), flush=True)
    if not args.no_open:
        webbrowser.open(result["url"])
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        manager().close()


if __name__ == "__main__":
    main()
