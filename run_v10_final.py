#!/usr/bin/env python3
"""
run_v10_final.py — Official Submission Harness for ARC DGM-lite v10 Final

Runs arc_dgmlite_v10a4_action6_router.py across specified ARC-AGI-3 games.
Saves per-game JSONL logs and a CSV summary.

Usage:
    python3 run_v10_final.py                          # all 25 games
    python3 run_v10_final.py tn36 sp80                # specific games
    python3 run_v10_final.py --max-steps 500 tn36     # custom steps

Output:
    arc_runs/v10_final_<game>.jsonl
    arc_runs/summary_v10_final.csv
    arc_runs/v10_final_benchmark.log
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

WORKDIR = Path("/a0/usr/workdir")
ARC_RUNS = WORKDIR / "arc_runs"
VERSION_FILE = WORKDIR / "arc_dgmlite_v10a4_action6_router.py"

DEFAULT_GAMES = [
    "ar25", "bp35", "cd82", "cn04", "dc22",
    "ft09", "g50t", "ka59", "lf52", "lp85",
    "ls20", "m0r0", "r11l", "re86", "s5i5",
    "sb26", "sc25", "sk48", "sp80", "su15",
    "tn36", "tr87", "tu93", "vc33", "wa30",
]


def setup_logging():
    """Configure logging to file and stdout."""
    ARC_RUNS.mkdir(parents=True, exist_ok=True)
    log_path = ARC_RUNS / "v10_final_benchmark.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(str(log_path)),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="ARC DGM-lite v10 Final Submission Harness")
    parser.add_argument("games", nargs="*", default=None, help="Game IDs to run (default: all 25)")
    parser.add_argument(
        "--max-steps", type=int, default=500,
        help="Maximum steps per game (default: 500)"
    )
    return parser.parse_args()


def import_router():
    """Import and return the router module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "arc_dgmlite_v10a4_action6_router",
        str(VERSION_FILE)
    )
    router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(router)
    return router


def run_game_safe(game_id, max_steps):
    """Run one game with v10_final and return metrics dict.

    Args:
        game_id: Game identifier (e.g., 'tn36')
        max_steps: Maximum exploration steps

    Returns:
        dict with keys: game, unique_states, levels_completed, archive_size,
                        zero_delta_rate, early_stagnation, action6_attempts,
                        action6_successes, status, duration
    """
    start_time = time.time()
    result = {
        "game": game_id,
        "unique_states": 0,
        "levels_completed": 0,
        "archive_size": 0,
        "zero_delta_rate": 1.0,
        "early_stagnation": 0,
        "action6_attempts": 0,
        "action6_successes": 0,
        "status": "ERROR",
        "duration": 0.0,
    }

    try:
        sys.path.insert(0, str(WORKDIR))
        router = import_router()

        # Run the game — run_game signature: (game_id, max_steps=500, out_dir='arc_runs', action6_mode=None)
        obs = router.run_game(game_id, max_steps=max_steps)

        # Extract metrics from FrameDataRaw or obs
        if hasattr(obs, "unique_states"):
            result["unique_states"] = obs.unique_states
        elif hasattr(obs, "archive") and hasattr(obs.archive, "size"):
            result["unique_states"] = obs.archive.size

        if hasattr(obs, "levels_completed"):
            result["levels_completed"] = obs.levels_completed

        if hasattr(obs, "archive") and hasattr(obs.archive, "cells"):
            result["archive_size"] = len(obs.archive.cells)

        if hasattr(obs, "zero_delta_rate"):
            result["zero_delta_rate"] = obs.zero_delta_rate

        if hasattr(obs, "early_stagnation"):
            result["early_stagnation"] = int(obs.early_stagnation)

        if hasattr(obs, "action6_attempts"):
            result["action6_attempts"] = obs.action6_attempts
        if hasattr(obs, "action6_successes"):
            result["action6_successes"] = obs.action6_successes

        state_str = str(getattr(obs, "state", ""))
        if "GAME_OVER" in state_str or "COMPLETED" in state_str:
            result["status"] = "GAME_OVER"
        elif "RUNNING" in state_str or "PLAYING" in state_str:
            result["status"] = "PARTIAL"
        else:
            result["status"] = "UNKNOWN"

    except Exception as e:
        result["status"] = f"CRASH: {str(e)[:80]}"
        logging.error(f"  Game {game_id} crashed: {e}")

    result["duration"] = round(time.time() - start_time, 2)
    return result


def save_jsonl_logs(arcade, game_id):
    """Save per-game JSONL log if arcade has logged transitions."""
    jsonl_path = ARC_RUNS / f"v10_final_{game_id}.jsonl"
    if hasattr(arcade, "log") and arcade.log:
        with open(str(jsonl_path), "w") as f:
            for entry in arcade.log:
                f.write(json.dumps(entry) + "\n")
        return True
    return False


def main():
    logger = setup_logging()
    args = parse_args()

    logger.info("=" * 60)
    logger.info("ARC DGM-lite v10 Final — Benchmark Runner")
    logger.info(f"Version file: {VERSION_FILE}")
    logger.info(f"Max steps per game: {args.max_steps}")

    games = args.games if args.games else DEFAULT_GAMES
    logger.info(f"Games: {len(games)} ({', '.join(games[:5])}...)")

    if not VERSION_FILE.exists():
        logger.error(f"Version file not found: {VERSION_FILE}")
        sys.exit(1)

    

    results = []
    total_start = time.time()

    for i, game_id in enumerate(games, 1):
        logger.info(f"[{i}/{len(games)}] Running {game_id}...")
        result = run_game_safe(game_id, args.max_steps)
        results.append(result)

        summary = (
            f"  → states={result['unique_states']}, "
            f"levels={result['levels_completed']}, "
            f"archive={result['archive_size']}, "
            f"zd={result['zero_delta_rate']:.3f}, "
            f"action6={result['action6_attempts']}, "
            f"status={result['status']}, "
            f"{result['duration']}s"
        )
        logger.info(summary)

    total_time = round(time.time() - total_start, 2)

    # Save summary CSV
    csv_path = ARC_RUNS / "summary_v10_final.csv"
    fieldnames = [
        "game", "unique_states", "levels_completed", "archive_size",
        "zero_delta_rate", "early_stagnation", "action6_attempts",
        "action6_successes", "status", "duration"
    ]
    with open(str(csv_path), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Summary
    completed = sum(1 for r in results if "CRASH" not in r["status"])
    crashed = sum(1 for r in results if "CRASH" in r["status"])
    if len(results) > 0:
        mean_states = sum(r["unique_states"] for r in results) / len(results)
        total_progress = sum(r["levels_completed"] for r in results)
    else:
        mean_states = 0
        total_progress = 0

    logger.info("=" * 60)
    logger.info(f"BENCHMARK COMPLETE — {total_time}s")
    logger.info(f"Games: {completed}/{len(games)} OK | Crashes: {crashed}")
    logger.info(f"Mean unique states: {mean_states:.2f}")
    logger.info(f"Total levels completed: {total_progress}")
    logger.info(f"Summary saved to: {csv_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
