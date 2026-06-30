import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wheredle.config import Config
from wheredle.db import connect
from wheredle.game import repository as repo


def main():
    """Dev helper: promote the oldest queued puzzle to live for today (Phase 4 automates this)."""
    config = Config.from_env()
    conn = connect(config.database_path)
    row = conn.execute("SELECT id FROM puzzles WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
    if row is None:
        print("no queued puzzles — run scripts/fetch_candidates.py first")
        return 1
    today = date.today().isoformat()
    repo.activate_puzzle(conn, row["id"], today)
    print(f"puzzle {row['id']} is now live for {today}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
