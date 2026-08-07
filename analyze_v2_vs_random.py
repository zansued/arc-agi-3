#!/usr/bin/env python3
"""
analyze_v2_vs_random.py — Análise comparativa automática DGM-lite v2 vs Random.

Lê:   arc_runs/v2_*.jsonl (v2), arc_runs/random_summary.csv (random)
Gera: arc_runs/comparison_v2_vs_random.csv
       arc_runs/evaluation_report.txt
"""
import os, sys, json, csv, io, math
from pathlib import Path
from collections import Counter

OUT_DIR = "arc_runs"

def load_random_summary(path):
    """Load random baseline summary CSV."""
    data = {}
    if not path.exists():
        print(f"WARNING: {path} not found. Random data unavailable.")
        return data
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            gid = row["game_id"]
            data[gid] = {
                "states": int(row["unique_states"]),
                "entropy": float(row.get("action_entropy", 0) or 0),
                "action_counts": json.loads(row.get("action_counts", "{}") or "{}"),
                "zero_delta": int(row.get("zero_delta_steps", 0)),
                "stuck": int(row.get("stuck_steps", 0)),
            }
    print(f"Loaded {len(data)} games from random summary.")
    return data

def load_v2_logs(arc_runs):
    """Load v2 JSONL logs, returning per-game summary."""
    games = {}
    for fpath in sorted(arc_runs.glob("v2_*.jsonl")):
        lines = fpath.read_text().strip().split("\n")
        if not lines:
            continue
        last = json.loads(lines[-1])
        gid = last["game_id"]
        total_steps = len(lines)
        first = json.loads(lines[0]) if len(lines) > 1 else last
        # Parse all steps
        steps_data = [json.loads(l) for l in lines]
        # Action counts
        action_counts = Counter()
        total_delta = 0
        zero_delta_steps = 0
        activity_families = Counter()
        action6_count = 0
        fallback_count = 0
        last_new_state_step = 0
        hashes_seen = set()
        for sd in steps_data:
            a = str(sd.get("action", ""))
            action_counts[a] += 1
            delta = sd.get("changed_pixels", 0) or 0
            total_delta += delta
            if delta == 0:
                zero_delta_steps += 1
            fam = sd.get("family", "")
            activity_families[fam] += 1
            if "6" in a or "ACTION6" in a:
                action6_count += 1
            if "RandomFallback" in fam or "Fallback" in fam:
                fallback_count += 1
            if sd.get("is_new_state", False):
                last_new_state_step = sd["step"]
        # Entropy
        total_acts = sum(action_counts.values())
        entropy = 0.0
        if total_acts > 0:
            for c in action_counts.values():
                p = c / total_acts
                if p > 0:
                    entropy -= p * math.log2(p)
        # Dominant action
        dominant_action = max(action_counts, key=action_counts.get) if action_counts else "?"
        dominant_pct = action_counts[dominant_action] / max(1, total_acts)
        # Stuck rate: count of consecutive state repetitions
        stuck_rate = sd.get("stagnation", 0) / max(1, total_steps)
        unique_set = set()
        for sd in steps_data:
            h = sd.get("after_hash", "")
            if h:
                unique_set.add(h)
        unique_states_v2 = len(unique_set)
        games[gid] = {
            "states": unique_states_v2,
            "steps": len(steps_data),
            "entropy": round(entropy, 3),
            "action_counts": dict(action_counts),
            "dominant_action": dominant_action,
            "dominant_pct": round(dominant_pct, 4),
            "total_delta": total_delta,
            "zero_delta_steps": zero_delta_steps,
            "zero_delta_rate": round(zero_delta_steps / max(1, total_steps), 4),
            "stuck_rate": round(stuck_rate, 4),
            "action6_count": action6_count,
            "fallback_count": fallback_count,
            "last_new_state_step": last_new_state_step,
            "last_family": last.get("family", ""),
            "status": last.get("status", "running"),
        }
    print(f"Loaded {len(games)} games from v2 logs.")
    return games

def compute_comparison(v2, random_data):
    """Build comparison table."""
    rows = []
    for gid in sorted(v2):
        v = v2[gid]
        r = random_data.get(gid, {})
        diff = v["states"] - r.get("states", 0)
        if diff > 0:
            winner = "v2"
        elif diff < 0:
            winner = "random"
        else:
            winner = "tie"
        rows.append({
            "game_id": gid,
            "unique_v2": v["states"],
            "unique_random": r.get("states", 0),
            "diff": diff,
            "winner": winner,
            "entropy_v2": v["entropy"],
            "entropy_random": r.get("entropy", 0),
            "dominant_action_v2": v["dominant_action"],
            "dominant_pct_v2": v["dominant_pct"],
            "stuck_rate_v2": v["stuck_rate"],
            "zero_delta_rate_v2": v["zero_delta_rate"],
            "action6_count": v["action6_count"],
            "fallback_count": v["fallback_count"],
            "last_new_state_step": v["last_new_state_step"],
            "status": v["status"],
        })
    return rows

def save_csv(rows, path):
    fields = [
        "game_id", "unique_v2", "unique_random", "diff", "winner",
        "entropy_v2", "entropy_random", "dominant_action_v2",
        "dominant_pct_v2", "stuck_rate_v2", "zero_delta_rate_v2",
        "action6_count", "fallback_count", "last_new_state_step", "status"
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Saved: {path}")

def generate_report(rows, path):
    total = len(rows)
    wins_v2 = sum(1 for r in rows if r["winner"] == "v2")
    wins_random = sum(1 for r in rows if r["winner"] == "random")
    ties = sum(1 for r in rows if r["winner"] == "tie")
    diffs = [r["diff"] for r in rows]
    median_diff = sorted(diffs)[len(diffs)//2] if diffs else 0
    mean_diff = sum(diffs)/len(diffs) if diffs else 0
    mean_entropy_v2 = sum(r["entropy_v2"] for r in rows)/total if total > 0 else 0
    mean_dominance_v2 = sum(r["dominant_pct_v2"] for r in rows)/total if total > 0 else 0
    games_with_action6 = sum(1 for r in rows if r["action6_count"] > 0)
    games_with_fallback = sum(1 for r in rows if r["fallback_count"] > 0)
    errors = sum(1 for r in rows if r["status"] != "running")
    # Outliers
    sorted_by_diff = sorted(rows, key=lambda r: r["diff"], reverse=True)
    top5_v2 = sorted_by_diff[:5]
    top5_random = sorted_by_diff[-5:] if sorted_by_diff else []
    low_last_state = [r for r in rows if r["last_new_state_step"] < 50]
    high_zero = [r for r in rows if r["zero_delta_rate_v2"] > 0.9]

    lines = []
    lines.append("="*70)
    lines.append("   ARC-AGI-3: DGM-lite v2 vs Random Baseline — RELATÓRIO FINAL")
    lines.append("="*70)
    lines.append(f"Data da análise: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Total de jogos: {total}")
    lines.append("")
    lines.append("--- RESUMO ESTATÍSTICO ---")
    lines.append(f"  v2 wins:       {wins_v2}/{total} ({100*wins_v2//total}%)")
    lines.append(f"  Random wins:   {wins_random}/{total} ({100*wins_random//total}%)")
    lines.append(f"  Ties:          {ties}/{total}")
    lines.append(f"  Median diff:   {median_diff:+d} states")
    lines.append(f"  Mean diff:     {mean_diff:+.2f} states")
    lines.append(f"  Mean entropy v2:  {mean_entropy_v2:.3f}")
    lines.append(f"  Mean dominance v2: {mean_dominance_v2:.3f}")
    lines.append(f"  Games with ACTION6: {games_with_action6}")
    lines.append(f"  Games with Fallback: {games_with_fallback}")
    lines.append(f"  No. errors/crashes: {errors}")
    lines.append("")
    lines.append("--- CRITÉRIO DE VITÓRIA ---")
    passed = 0
    total_criteria = 5
    if wins_v2 >= max(1, total*15//25):
        lines.append(f"  ✅ v2 wins >= {total*15//25}/{total} (15/25): {wins_v2} ✓")
        passed += 1
    else:
        lines.append(f"  ❌ v2 wins >= {total*15//25}/{total}: {wins_v2} ✗")
    if median_diff > 0:
        lines.append(f"  ✅ median_diff > 0: {median_diff:+d} ✓")
        passed += 1
    else:
        lines.append(f"  ❌ median_diff > 0: {median_diff:+d} ✗")
    if mean_entropy_v2 >= 1.5:
        lines.append(f"  ✅ mean_entropy_v2 >= 1.5: {mean_entropy_v2:.2f} ✓")
        passed += 1
    else:
        lines.append(f"  ❌ mean_entropy_v2 >= 1.5: {mean_entropy_v2:.2f} ✗")
    if mean_dominance_v2 < 0.65:
        lines.append(f"  ✅ mean_dominance_v2 < 0.65: {mean_dominance_v2:.2f} ✓")
        passed += 1
    else:
        lines.append(f"  ❌ mean_dominance_v2 < 0.65: {mean_dominance_v2:.2f} ✗")
    if errors == 0:
        lines.append(f"  ✅ Zerro errors: ✓")
        passed += 1
    else:
        lines.append(f"  ❌ {errors} error(s) ✗")

    result = "PASSOU" if passed == total_criteria else f"PARCIAL ({passed}/{total_criteria})"
    lines.append(f"\n  RESULTADO FINAL: {result}")
    lines.append("")

    lines.append("--- TABELA COMPARATIVA ---")
    header = f"{'Game':20s} {'v2':6s} {'Rand':6s} {'Diff':6s} {'Winner':10s} {'H_v2':6s} {'H_rand':6s} {'DomAct':8s} {'Dom%':6s}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in sorted_by_diff:
        wn = {"v2": "✅ v2", "random": "🔴 Random", "tie": "⚖️ Tie"}.get(r["winner"], "?")
        lines.append(f"{r['game_id'][:18]:20s} {r['unique_v2']:4d} vs {r['unique_random']:4d} {r['diff']:+5d} {wn:10s} {r['entropy_v2']:.2f}  {r['entropy_random']:.2f}  {r['dominant_action_v2'][:6]:8s} {r['dominant_pct_v2']:.2f}")
    lines.append("")

    lines.append("--- OUTLIERS ---")
    lines.append(f"Top 5 v2 over random (maior diff positiva):")
    for r in top5_v2:
        lines.append(f"  🏆 {r['game_id'][:18]:20s} Δ={r['diff']:+d}")
    lines.append(f"\nTop 5 random over v2 (maior diff negativa):")
    for r in top5_random:
        if r['diff'] < 0:
            lines.append(f"  ⚠️ {r['game_id'][:18]:20s} Δ={r['diff']:+d}")
    if low_last_state:
        lines.append(f"\nJogos com last_new_state_step < 50 (pouca exploração tardia):")
        for r in low_last_state:
            lines.append(f"  ⚠️ {r['game_id'][:18]:20s} last_step={r['last_new_state_step']}, zero_delta={r['zero_delta_rate_v2']:.2f}")
    if high_zero:
        lines.append(f"\nJogos com zero_delta_rate > 0.9 (quase sem mudança visual):")
        for r in high_zero:
            lines.append(f"  ⚠️ {r['game_id'][:18]:20s} rate={r['zero_delta_rate_v2']:.2f}")
    lines.append("")

    # Write
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Saved: {path}")
    print("\n".join(lines))

def main():
    arc_runs = Path(OUT_DIR)
    random_path = arc_runs / "random_summary.csv"
    v2_path = arc_runs / "v2_*.jsonl"
    out_csv = arc_runs / "comparison_v2_vs_random.csv"
    out_txt = arc_runs / "evaluation_report.txt"
    print("=" * 70)
    print("   ARC-AGI-3: DGM-lite v2 vs Random Baseline")
    print("=" * 70)
    random_data = load_random_summary(random_path)
    v2_data = load_v2_logs(arc_runs)
    if not v2_data:
        print("ERROR: No v2 JSONL logs found. Run DGM-lite v2 benchmark first.")
        sys.exit(1)
    rows = compute_comparison(v2_data, random_data)
    save_csv(rows, out_csv)
    generate_report(rows, out_txt)

if __name__ == "__main__":
    main()
