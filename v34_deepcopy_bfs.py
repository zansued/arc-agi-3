#!/usr/bin/env python3
"""
v34 — Deepcopy BFS with Adaptive Beam + Action Prioritization + Fallback Router
"""
import copy
import hashlib
import json
import os
import random
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

MAX_STEPS = 500
MAX_PLY = 10
MAX_TOTAL_STATES = 4000
STAGNATION_WINDOW = 60
ACTION_ORDER = [1, 4, 5, 2, 3, 6]
ACTION6_DATA = {"x": 32, "y": 32}
WORKERS = 8

ALL_GAME_IDS = [
    "bp35", "cd82", "cn04", "ft09", "g50t",
    "ho59", "kf97", "lp85", "ls20", "oi61",
    "ol71", "or88", "re15", "re86", "sa47",
    "sc25", "sm82", "sp80", "tn36", "tr87",
    "tu40", "tu93", "wa30", "wy52", "xm16",
]

OUTPUT_DIR = "/a0/usr/workdir/arc_runs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "v34_full_summary.csv")
REPORT_PATH = os.path.join(OUTPUT_DIR, "v34_full_report.jsonl")


def frame_hash(fd):
    if fd is None or not hasattr(fd, "frame") or not fd.frame:
        return "none"
    return hashlib.md5(fd.frame[0].tobytes()).hexdigest()


def step_safe(game, action_id):
    try:
        if action_id == 6:
            return game.step(action_id, data=ACTION6_DATA)
        return game.step(action_id)
    except Exception:
        return None


def bfs_solve(game_id, max_steps=MAX_STEPS, max_ply=MAX_PLY):
    arcade = Arcade()
    try:
        game = arcade.make(game_id)
    except Exception as e:
        return {"game_id": game_id, "error": "make() failed: " + str(e),
                "states": 0, "levels": 0, "steps": 0, "crashes": 999,
                "dead": True, "fallback_used": "none"}

    fd = game.reset()
    root_hash = frame_hash(fd)
    if root_hash == "none":
        return {"game_id": game_id, "error": "reset() returned None",
                "states": 0, "levels": 0, "steps": 0, "crashes": 999,
                "dead": True}

    visited = {root_hash: fd.levels_completed if hasattr(fd, "levels_completed") else 0}
    frontier = deque()
    frontier.append((copy.deepcopy(game), (), 0, fd, root_hash))
    best_levels = fd.levels_completed if hasattr(fd, "levels_completed") else 0
    best_seq = ()
    total_steps = 0
    total_crashes = 0
    expansion_count = 0
    stagnation = 0
    fallback_used = "none"
    fd_node = fd

    while frontier and total_steps < max_steps and len(visited) < MAX_TOTAL_STATES:
        if len(frontier) > 500:
            frontier = deque(list(frontier)[:200])

        node = frontier.popleft()
        wrapper, seq, depth, fd_node, node_hash = node
        expansion_count += 1

        if depth >= max_ply:
            continue

        for action_id in ACTION_ORDER:
            if total_steps >= max_steps:
                break
            total_steps += 1

            try:
                new_wrapper = copy.deepcopy(wrapper)
            except Exception:
                total_crashes += 1
                continue

            new_fd = step_safe(new_wrapper, action_id)
            if new_fd is None:
                total_crashes += 1
                continue

            new_hash = frame_hash(new_fd)
            if new_hash == "none" or new_hash in visited:
                continue

            new_lv = new_fd.levels_completed if hasattr(new_fd, "levels_completed") else 0
            visited[new_hash] = new_lv
            new_seq = seq + (action_id,)
            frontier.append((new_wrapper, new_seq, depth + 1, new_fd, new_hash))

            if new_lv > best_levels:
                best_levels = new_lv
                best_seq = new_seq
                stagnation = 0
            else:
                stagnation += 1

        if stagnation > STAGNATION_WINDOW or (len(visited) < 10 and expansion_count > 5):
            fallback_used = "random_perturbation"
            if len(frontier) > 10:
                idx = random.randint(0, min(len(frontier) // 2, 50))
                frontier.rotate(-idx)
            stagnation = 0

    if len(visited) <= 1:
        dead = True
        fallback_used = "action1_only"
        wrapper2 = game
        wrapper2.reset()
        for _ in range(100):
            if total_steps >= max_steps:
                break
            try:
                fd2 = wrapper2.step(1)
                total_steps += 1
                if fd2:
                    h2 = frame_hash(fd2)
                    if h2 != "none" and h2 not in visited:
                        lv2 = fd2.levels_completed if hasattr(fd2, "levels_completed") else 0
                        visited[h2] = lv2
                        if lv2 > best_levels:
                            best_levels = lv2
            except Exception:
                total_crashes += 1

        if len(visited) <= 1:
            fallback_used = "all_actions_with_data"
            wrapper2.reset()
            for a_try in range(1, 7):
                for _ in range(30):
                    if total_steps >= max_steps:
                        break
                    try:
                        fd2 = step_safe(wrapper2, a_try)
                        total_steps += 1
                        if fd2:
                            h2 = frame_hash(fd2)
                            if h2 != "none" and h2 not in visited:
                                visited[h2] = fd2.levels_completed if hasattr(fd2, "levels_completed") else 0
                    except Exception:
                        total_crashes += 1

        if len(visited) <= 1:
            fallback_used = "noop"
            for _ in range(50):
                if total_steps >= max_steps:
                    break
                try:
                    fd2 = wrapper2.step(0)
                    total_steps += 1
                    if fd2:
                        h2 = frame_hash(fd2)
                        if h2 != "none" and h2 not in visited:
                            visited[h2] = fd2.levels_completed if hasattr(fd2, "levels_completed") else 0
                except Exception:
                    total_crashes += 1
    else:
        dead = False

    win_levels = fd_node.win_levels if hasattr(fd_node, "win_levels") else 0
    return {
        "game_id": game_id,
        "states": len(visited),
        "levels": best_levels,
        "win_levels": win_levels,
        "steps": total_steps,
        "crashes": total_crashes,
        "expansion_count": expansion_count,
        "best_seq": str(best_seq),
        "dead": dead,
        "fallback_used": fallback_used,
        "error": None,
    }


def run_game(game_id):
    start = time.time()
    try:
        result = bfs_solve(game_id)
        elapsed = time.time() - start
        result["elapsed_sec"] = round(elapsed, 1)
        return result
    except Exception as e:
        return {
            "game_id": game_id,
            "error": str(e),
            "states": 0, "levels": 0, "steps": 0, "crashes": 999,
            "dead": True, "fallback_used": "none",
            "elapsed_sec": round(time.time() - start, 1),
        }


def main():
    print("=" * 60)
    print("V34 — DEEPCOPY BFS WITH ADAPTIVE BEAM + FALLBACK")
    print("Games: " + str(len(ALL_GAME_IDS)) + ", Workers: " + str(WORKERS))
    print("Max steps/game: " + str(MAX_STEPS) + ", Max ply: " + str(MAX_PLY))
    print("=" * 60)
    print()

    all_results = []
    total_states = 0
    total_levels = 0
    total_steps = 0
    total_crashes = 0
    dead_games = []
    alive_games = []
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(run_game, gid): gid for gid in ALL_GAME_IDS}
        for future in as_completed(futures):
            r = future.result()
            all_results.append(r)
            total_states += r["states"]
            total_levels += r["levels"]
            total_steps += r["steps"]
            total_crashes += r["crashes"]
            if r["dead"]:
                dead_games.append(r["game_id"])
            else:
                alive_games.append(r["game_id"])

            line = (
                "[" + time.strftime("%H:%M:%S") + "] " +
                "{:6s}".format(r["game_id"]) + " | " +
                "states={:4d}".format(r["states"]) + "  " +
                "levels={}".format(r["levels"]) + "  " +
                "steps={:4d}".format(r["steps"]) + "  " +
                "cr={:3d}".format(r["crashes"]) + "  " +
                "fb={:12s}".format(r["fallback_used"][:12]) + "  " +
                "{:5.1f}s".format(r["elapsed_sec"])
            )
            if r.get("error"):
                line += "  ERROR: " + str(r["error"])[:40]
            print(line)

    all_results.sort(key=lambda x: x["game_id"])
    avg_states = total_states / len(ALL_GAME_IDS) if ALL_GAME_IDS else 0

    print()
    print("=" * 60)
    print("V34 FULL BENCHMARK SUMMARY")
    print("=" * 60)
    print("Games completed: " + str(len(all_results)) + "/" + str(len(ALL_GAME_IDS)))
    print("Total unique states: " + str(total_states) + " (avg " + str(round(avg_states, 1)) + ")")
    print("Total levels: " + str(total_levels))
    print("Dead games (1 state): " + str(len(dead_games)) + " — " + ", ".join(dead_games))
    print("Alive games: " + str(len(alive_games)))
    print()

    sorted_by_states = sorted(all_results, key=lambda x: -x["states"])
    print("Top state discoverers:")
    for r in sorted_by_states[:10]:
        print("  {:6s}: {:4d} states, {} levels, {:4d} steps".format(r["game_id"], r["states"], r["levels"], r["steps"]))
    print()

    print("Per-game detail:")
    print("{:6s}  {:>6s}  {:>6s}  {:>6s}  {:>6s}  {:16s}".format("Game", "States", "Levels", "Steps", "Crash", "Fallback"))
    print("-" * 80)
    for r in sorted_by_states:
        print("{:6s}  {:6d}  {:6d}  {:6d}  {:6d}  {:16s}".format(
            r["game_id"], r["states"], r["levels"], r["steps"], r["crashes"], r["fallback_used"]))

    try:
        with open(SUMMARY_PATH, "w") as f:
            f.write("game_id,states,levels,steps,crashes,dead,fallback,error\n")
            for r in all_results:
                f.write("{},{},{},{},{},{},{},{}\n".format(
                    r["game_id"], r["states"], r["levels"],
                    r["steps"], r["crashes"], r["dead"],
                    r["fallback_used"], r.get("error", "")))
        print("\nCSV written: " + SUMMARY_PATH)
    except Exception as e:
        print("CSV write error: " + str(e))

    try:
        with open(REPORT_PATH, "w") as f:
            f.write(json.dumps({
                "run_key": "v34_full_benchmark",
                "timestamp": timestamp,
                "total_games": len(all_results),
                "total_states": total_states,
                "total_levels": total_levels,
                "dead_games": dead_games,
            }, indent=2))
        print("Report written: " + REPORT_PATH)
    except Exception as e:
        print("Report write error: " + str(e))

    report_to_supervisor({
        "event": "v34_complete",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_states": total_states,
        "total_levels": total_levels,
        "dead_games": dead_games,
    })

    return all_results


def report_to_supervisor(data):
    path = "/a0/usr/workdir/v34_report.jsonl"
    try:
        with open(path, "a") as f:
            f.write(json.dumps(data) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
