#!/usr/bin/env python3
"""Reset local demo databases and/or regenerate PostgreSQL seed SQL.

  python scripts/seed_demo_data.py              # reset local SQLite demo stores
  python scripts/seed_demo_data.py --postgres   # regenerate database/postgres/*_seed.sql
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adk_shared.seed import reset_local_databases, write_postgres_seeds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres", action="store_true",
                        help="regenerate PostgreSQL seed SQL files")
    args = parser.parse_args()
    if args.postgres:
        for path in write_postgres_seeds():
            print(f"wrote {path}")
    else:
        for name, path in reset_local_databases().items():
            print(f"reset {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
