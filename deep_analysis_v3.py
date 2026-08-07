#!/usr/bin/env python3
"""
Deep Analysis: DGM-lite v3 Progress-Aware

Para cada jogo:
- unique_states, entropy, dominant_action
- zero_delta_rate, last_new_state_step
- action6_count, action6_mean_delta
- best_action_by_delta, best_action_by_new_states
- state_transitions
- max_levels_completed, win_levels, progress_ratio

Tabelas:
- action -> mean changed_pixels
- action -> prob new_state
- action -> prob new_available_action
- action -> prob fail
- ACTION6 by region
"""
import os, json, csv, glob, math
from collections import Counter, defaultdict, deque
import numpy as np

OUT_DIR = "arc_runs"
ROOT = "/a0/usr/workdir"

def load_v3_logs():
    logs = {}
    pattern = os.path.join(ROOT, OUT_DIR, "v3_*.jsonl")
    for fpath in sorted(glob.glob(pattern)):
        gid = os.path.basename(fpath).replace("v3_", "").replace(".jsonl", "")
        with open(fpath) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        logs[gid] = lines
    return logs

def analyze_game(lines, gid):
    if not lines:
        return {}
    unique_by_hash = set()
    action_pixel_deltas = defaultdict(list)
    action_new_state = defaultdict(int)
    action_total = Counter()
    action_new_avail = defaultdict(int)
    action_fail = defaultdict(int)
    action6_by_region = defaultdict(list)
    hash_sequence = []
    last_new_state_step = 0
    zero_delta_steps = 0
    new_avail_count = 0
    fail_count = 0
    action6_total = 0
    prev_avail = set()
    max_levels = 0
    win_levels = 1
    best_progress = 0.0
    action_unlock_events = 0
    action_lock_events = 0
    for i, l in enumerate(lines):
        step = i
        action_key = l.get("action_key", str(l.get("action", "?")))
        data = l.get("data")
        before_hash = l.get("before_hash", "")
        after_hash = l.get("after_hash", "")
        changed = int(l.get("changed_pixels", 0))
        is_new = l.get("is_new_state", False)
        avail = l.get("available_actions", [])
        family = l.get("family", "")
        levels = int(l.get("levels_completed", 0))
        win = int(l.get("win_levels", 1))
        state_str = l.get("state", "")
        progress = float(l.get("progress_ratio", 0.0))
        # Track progress
        if levels > max_levels:
            max_levels = levels
        if win > win_levels:
            win_levels = win
        if progress > best_progress:
            best_progress = progress
        # Hash tracking
        if after_hash and after_hash not in unique_by_hash:
            unique_by_hash.add(after_hash)
            last_new_state_step = step
        hash_sequence.append(after_hash)
        # Zero delta
        if changed == 0:
            zero_delta_steps += 1
        # Action stats
        if "ACTION" in action_key or action_key.startswith("A"):
            action_total[action_key] += 1
            action_pixel_deltas[action_key].append(changed)
            if is_new:
                action_new_state[action_key] += 1
            # action unlock/lock detection
            curr_avail = set(str(a) for a in avail) if avail else set()
            if prev_avail:
                if curr_avail - prev_avail:
                    action_unlock_events += 1
                if prev_avail - curr_avail:
                    action_lock_events += 1
            prev_avail = curr_avail if avail else prev_avail
            # Fail detection
            if "FAIL" in state_str.upper():
                action_fail[action_key] += 1
                fail_count += 1
            # ACTION6 by region
            if "ACTION6" in action_key and data:
                action6_total += 1
                x = data.get("x", 32) if isinstance(data, dict) else 32
                y = data.get("y", 32) if isinstance(data, dict) else 32
                if abs(x-32) <= 16 and abs(y-32) <= 16:
                    region = "center"
                elif x <= 8 or y <= 8 or x >= 55 or y >= 55:
                    region = "edge"
                elif 8 <= x <= 55 and 8 <= y <= 55:
                    region = "foreground"
                else:
                    region = "other"
                action6_by_region[region].append(changed)
    # Compute metrics
    total_steps = len(lines)
    zero_delta_rate = zero_delta_steps / max(1, total_steps)
    # State transitions
    transitions = Counter()
    for i in range(1, len(hash_sequence)):
        key = f"{hash_sequence[i-1][:8]}->{hash_sequence[i][:8]}"
        # Just count distinct transitions
    # Entropy
    tot_acts = sum(action_total.values())
    ent = 0.0
    dominant_action = ""
    dominant_pct = 0.0
    if tot_acts > 0:
        for act, cnt in action_total.items():
            p = cnt / tot_acts
            if p > dominant_pct:
                dominant_pct = p
                dominant_action = act
            if p > 0:
                ent -= p * math.log2(p)
    # Best action by mean delta
    best_action_delta = ""
    best_delta_val = -1
    best_action_new = ""
    best_new_val = -1
    for act, deltas in action_pixel_deltas.items():
        if deltas:
            md = sum(deltas) / len(deltas)
            if md > best_delta_val:
                best_delta_val = md
                best_action_delta = act
    for act, cnt in action_new_state.items():
        total_act = action_total[act]
        prob = cnt / max(1, total_act)
        if prob > best_new_val and total_act >= 3:
            best_new_val = prob
            best_action_new = act
    # Action6 mean delta
    action6_deltas = action_pixel_deltas.get("ACTION6", [])
    action6_mean_delta = sum(action6_deltas) / max(1, len(action6_deltas)) if action6_deltags else 0
    state_transition_count = len(transitions)
    return {
        "game_id": gid,
        "total_steps": total_steps,
        "unique_states": len(unique_by_hash),
        "entropy": round(ent, 3),
        "dominant_action": dominant_action,
        "dominant_pct": round(dominant_pct, 3),
        "zero_delta_rate": round(zero_delta_rate, 4),
        "last_new_state_step": last_new_state_step,
        "action6_count": action6_total,
        "action6_mean_delta": round(action6_mean_delta, 2),
        "best_action_by_delta": f"{best_action_delta}({best_delta_val:.1f})" if best_action_delta else "none",
        "best_action_by_new_state": f"{best_action_new}({best_new_val:.2f})" if best_action_new else "none",
        "max_levels_completed": max_levels,
        "win_levels": win_levels,
        "progress_ratio": round(best_progress, 4),
        "action_unlock_events": action_unlock_events,
        "action_lock_events": action_lock_events,
        "fail_count": fail_count,
        "action_table": {
            act: {
                "count": cnt,
                "mean_delta": round(sum(action_pixel_deltas.get(act, [0])) / max(1, len(action_pixel_deltas.get(act, [0]))), 2) if action_pixel_deltas.get(act) else 0,
                "new_state_prob": round(action_new_state.get(act, 0) / max(1, cnt), 4),
                "fail_prob": round(action_fail.get(act, 0) / max(1, cnt), 4),
            }
            for act, cnt in action_total.most_common()
        },
        "action6_regions": {
            reg: {
                "count": len(deltas),
                "mean_delta": round(sum(deltas) / max(1, len(deltas)), 2)
            }
            for reg, deltas in sorted(action6_by_region.items())
        } if action6_by_region else {},
    }

def print_report(results):
    print("=" * 90)
    print("📊 DEEP ANALYSIS: DGM-lite v3 Progress-Aware (25 jogos)")
    print("=" * 90)
    games_with_action6 = sum(1 for r in results if r.get("action6_count",0) > 0)
    games_with_fail = sum(1 for r in results if r.get("fail_count",0) > 0)
    print(f"\n📈 GLOBAL STATS:")
    print(f"  Games: {len(results)}")
    print(f"  Games with ACTION6 use: {games_with_action6}")
    print(f"  Games with FAIL: {games_with_fail}")
    print(f"  Games with progress > 0: {sum(1 for r in results if r.get('progress_ratio',0) > 0)}")
    print(f"  Mean entropy: {sum(r['entropy'] for r in results)/max(1,len(results)):.3f}")
    print(f"  Mean states: {sum(r['unique_states'] for r in results)/max(1,len(results)):.1f}")
    print(f"  Mean zero_delta_rate: {sum(r['zero_delta_rate'] for r in results)/max(1,len(results)):.4f}")
    # Top 10
    print(f"\n🏆 TOP 10 MOST EXPLORED:")
    sorted_r = sorted(results, key=lambda r: -r['unique_states'])
    for i,r in enumerate(sorted_r[:10]):
        print(f"  {i+1}. {r['game_id'][:20]:20s} states={r['unique_states']:>4} entropy={r['entropy']:.2f} "
              f"dominant={r['dominant_action'][:10]:10s}({r['dominant_pct']:.2%}) "
              f"last_new={r['last_new_state_step']:>4}")
    # Stuck analysis
    early_stuck = [r for r in results if r['last_new_state_step'] < 100]
    late_discovery = [r for r in results if r['last_new_state_step'] > 400]
    high_zero = [r for r in results if r['zero_delta_rate'] > 0.9]
    action6_high = [r for r in results if r['action6_count'] > 50 and r['action6_mean_delta'] > 10]
    print(f"\n🪤 STAGNATION ANALYSIS:")
    print(f"  Last new state < 100 steps: {len(early_stuck)} games")
    print(f"  Last new state > 400 steps: {len(late_discovery)} games")
    print(f"  Zero delta rate > 90%: {len(high_zero)} games")
    print(f"  ACTION6 useful (>50 calls, >10 mean delta): {len(action6_high)} games")
    if early_stuck:
        print(f"  Early-stuck games:")
        for r in early_stuck[:5]:
            print(f"    {r['game_id'][:20]:20s} last_new={r['last_new_state_step']:>4} zerodel={r['zero_delta_rate']:.2%}")
    # Fail analysis
    fail_games = [r for r in results if r['fail_count'] > 0]
    print(f"\n💀 FAIL ANALYSIS:")
    print(f"  Games with any FAIL: {len(fail_games)}")
    for r in fail_games[:5]:
        print(f"    {r['game_id'][:20]:20s} fails={r['fail_count']}")
    # ACTION6 analysis
    print(f"\n🎯 ACTION6 BY REGION (across all games):")
    region_agg = defaultdict(list)
    for r in results:
        for reg, data in r.get('action6_regions',{}).items():
            region_agg[reg].append(data['mean_delta'])
    for reg, deltas in sorted(region_agg.items()):
        print(f"  {reg:15s}: mean_delta={sum(deltas)/len(deltas):.2f} across {len(deltas)} games")
    # Best action stats across all games
    print(f"\n🎮 BEST ACTIONS BY GAME:")
    for r in sorted_r[:10]:
        acts = r.get('action_table', {})
        print(f"\n  {r['game_id'][:20]} (states={r['unique_states']}, ent={r['entropy']}):")
        sorted_acts = sorted(acts.items(), key=lambda x: -x[1]['count'])[:5]
        for act, stats in sorted_acts:
            print(f"    {act:12s}: count={stats['count']:>3} mean_delta={stats['mean_delta']:>6.1f} "
                  f"new_state={stats['new_state_prob']:.2%} fail={stats['fail_prob']:.2%}")

def save_csv(results):
    fpath = os.path.join(ROOT, OUT_DIR, "deep_analysis_v3.csv")
    fields = ["game_id","total_steps","unique_states","entropy",
              "dominant_action","dominant_pct","zero_delta_rate",
              "last_new_state_step","action6_count","action6_mean_delta",
              "best_action_by_delta","best_action_by_new_state",
              "max_levels_completed","win_levels","progress_ratio",
              "action_unlock_events","action_lock_events","fail_count"]
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            row = {k: r.get(k, "") for k in fields}
            w.writerow(row)
    print(f"\n💾 CSV saved: {fpath}")
    return fpath

def main():
    logs = load_v3_logs()
    print(f"Loaded {len(logs)} game logs from {OUT_DIR}/v3_*.jsonl")
    results = []
    for gid in sorted(logs.keys()):
        r = analyze_game(logs[gid], gid)
        results.append(r)
    results.sort(key=lambda x: -x['unique_states'])
    print_report(results)
    save_csv(results)
    with open(os.path.join(ROOT, OUT_DIR, "deep_analysis_v3.txt"), "w") as f:
        import sys
        old = sys.stdout
        class Tee:
            def __init__(self, *files):
                self.files = files
            def write(self, obj):
                for file in self.files:
                    file.write(obj)
                    file.flush()
            def flush(self):
                for file in self.files:
                    file.flush()
        with open(os.path.join(ROOT, OUT_DIR, "deep_analysis_v3.txt"), "w") as rf:
            tee = Tee(sys.stdout, rf)
            sys.stdout = tee
            print_report(results)
            sys.stdout = old
    print(f"\n✅ Deep Analysis complete!")
    return results

if __name__ == "__main__":
    main()
