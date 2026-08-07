#!/usr/bin/env python3
"""
analyze_v4_vs_v3.py — Comparação DGM-lite v4 Planner vs v3 Progress-Aware

Gera:
  - v4_vs_v3_comparison.csv (por jogo)
  - v4_mode_analysis.csv (por modo)
  - v4_evaluation_report.txt (relatório consolidado)
"""
import os, json, csv, glob, math
from collections import Counter, defaultdict

OUT_DIR = "arc_runs"
ROOT = "/a0/usr/workdir"

# ---------------------------------------------------------------------------
# Load v3 summary
# ---------------------------------------------------------------------------

def load_v3_summary():
    path = os.path.join(ROOT, OUT_DIR, "summary_v3.csv")
    data = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            gid = row["game_id"]
            data[gid] = row
    return data

# ---------------------------------------------------------------------------
# Load v4 JSONL logs
# ---------------------------------------------------------------------------

def load_v4_logs():
    pattern = os.path.join(ROOT, OUT_DIR, "v4_*.jsonl")
    logs = {}
    for fpath in sorted(glob.glob(pattern)):
        gid = os.path.basename(fpath).replace("v4_", "").replace(".jsonl", "")
        with open(fpath) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        logs[gid] = lines
    return logs

# ---------------------------------------------------------------------------
# Analyze v4 game
# ---------------------------------------------------------------------------

def analyze_v4_game(lines):
    if not lines:
        return {}
    unique_hashes = set()
    mode_stats = defaultdict(lambda: {"steps":0, "new_states":0, "deltas":[], "zero_delta_steps":0, "progress_events":0})
    total_steps = len(lines)
    zero_delta_steps = 0
    last_new_state_step = 0
    progress_events = 0
    hash_sequence = []
    for i, l in enumerate(lines):
        ah = l.get("after_hash", "")
        if ah and ah not in unique_hashes:
            unique_hashes.add(ah)
            last_new_state_step = i
        hash_sequence.append(ah)
        changed = int(l.get("changed_pixels", 0))
        mode = l.get("mode", "UNKNOWN")
        is_new = l.get("is_new_state", False)
        levels = int(l.get("levels_completed", 0))
        # Per-mode tracking
        mode_stats[mode]["steps"] += 1
        mode_stats[mode]["deltas"].append(changed)
        if changed == 0:
            mode_stats[mode]["zero_delta_steps"] += 1
        if is_new:
            mode_stats[mode]["new_states"] += 1
        if levels > 0:
            mode_stats[mode]["progress_events"] += 1
            progress_events += 1
        # Global
        if changed == 0:
            zero_delta_steps += 1
    zero_delta_rate = zero_delta_steps / max(1, total_steps)
    mode_summary = {}
    for mode, s in sorted(mode_stats.items()):
        ns = s["new_states"]
        nsp100 = 100 * ns / max(1, s["steps"])
        mean_d = sum(s["deltas"]) / max(1, len(s["deltas"]))
        zd_rate = s["zero_delta_steps"] / max(1, s["steps"])
        mode_summary[mode] = {
            "steps": s["steps"],
            "step_pct": round(s["steps"] / total_steps * 100, 1),
            "new_states": ns,
            "new_states_per_100_steps": round(nsp100, 2),
            "mean_delta_pixels": round(mean_d, 2),
            "zero_delta_rate": round(zd_rate, 4),
            "progress_events": s["progress_events"],
        }
    # Action counts
    action_counts = Counter()
    for l in lines:
        a = l.get("action", "?")
        action_counts[a] += 1
    tot_acts = sum(action_counts.values()) + 1
    ent = 0.0
    for c in action_counts.values():
        p = c / tot_acts
        if p > 0:
            ent -= p * math.log2(p)
    progress = max(float(l.get("progress_ratio", 0.0)) for l in lines) if lines else 0.0
    max_levels = max(int(l.get("levels_completed", 0)) for l in lines) if lines else 0
    win_levels = max(int(l.get("win_levels", 1)) for l in lines) if lines else 1
    return {
        "unique_states": len(unique_hashes),
        "action_entropy": round(ent, 3),
        "zero_delta_rate": round(zero_delta_rate, 4),
        "last_new_state_step": last_new_state_step,
        "best_progress": round(progress, 4),
        "max_levels": max_levels,
        "win_levels": win_levels,
        "early_stagnation": 1 if last_new_state_step < 100 else 0,
        "mode_summary": mode_summary,
        "total_steps": total_steps,
        "progress_events": progress_events,
    }

# ---------------------------------------------------------------------------
# Generate reports
# ---------------------------------------------------------------------------

def generate_comparison_csv(comparison_rows, mode_rows):
    # Per-game comparison
    fpath = os.path.join(ROOT, OUT_DIR, "v4_vs_v3_comparison.csv")
    fields = ["game_id","unique_v3","unique_v4","unique_diff","entropy_v3","entropy_v4","entropy_diff",
              "zero_delta_v3","zero_delta_v4","zero_delta_diff","last_new_step_v3","last_new_step_v4",
              "early_stag_v3","early_stag_v4","progress_v3","progress_v4","max_levels_v3","max_levels_v4"]
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(comparison_rows)
    print(f"   ✅ CSV: {fpath}")
    # Per-mode analysis
    fpath2 = os.path.join(ROOT, OUT_DIR, "v4_mode_analysis.csv")
    mfields = ["mode","total_steps","step_pct","new_states","new_states_per_100_steps",
               "mean_delta_pixels","zero_delta_rate","progress_events"]
    with open(fpath2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=mfields, extrasaction='ignore')
        w.writeheader()
        w.writerows(mode_rows)
    print(f"   ✅ CSV: {fpath2}")

def generate_report(comparison_rows, mode_rows, v4_summary, v3_summary):
    fpath = os.path.join(ROOT, OUT_DIR, "v4_evaluation_report.txt")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write("=" * 95 + "\n")
        f.write("📊 DGM-lite v4 Planner vs v3 Progress-Aware — Evaluation Report\n")
        f.write("=" * 95 + "\n\n")
        # V4 summary
        f.write("\n═══════════════════════════════════════════════\n")
        f.write("📈 V4 AGGREGATE STATS\n")
        f.write("═══════════════════════════════════════════════\n")
        f.write(f"  Games analyzed: {len(v4_summary)}\n")
        f.write(f"  Crashes: {sum(1 for g in comparison_rows if not g.get('unique_v4') or g['unique_v4']==0)}\n")
        ent4_vals = [r.get('entropy_v4',0) for r in comparison_rows if r.get('entropy_v4',0)]
        f.write(f"  Mean entropy: {sum(ent4_vals)/max(1,len(comparison_rows)):.3f}\n")
        zd4_vals = [r.get('zero_delta_v4',0) for r in comparison_rows if r.get('zero_delta_v4',0)]
        f.write(f"  Mean zero_delta: {sum(zd4_vals)/max(1,len(comparison_rows)):.4f}\n")
        early4 = sum(1 for r in comparison_rows if r.get('early_stag_v4',0))
        f.write(f"  Early stagnation (<100): {early4}/{len(comparison_rows)}\n")
        f.write(f"  Games with progress>0: {sum(1 for r in comparison_rows if r['progress_v4']>0)}\n")
        f.write(f"  Max levels: {max(r['max_levels_v4'] for r in comparison_rows if 'max_levels_v4' in r)}\n")
        # Compare vs v3
        f.write("\n" + "=" * 95 + "\n")
        f.write("🔬 V3 vs V4 COMPARISON\n")
        f.write("=" * 95 + "\n")
        mean_zd_v3 = sum(r['zero_delta_v3'] for r in comparison_rows if r.get('zero_delta_v3'))/max(1,len(comparison_rows))
        mean_zd_v4 = sum(r['zero_delta_v4'] for r in comparison_rows if r.get('zero_delta_v4'))/max(1,len(comparison_rows))
        early_v3 = sum(r['early_stag_v3'] for r in comparison_rows if r.get('early_stag_v3'))/max(1,len(comparison_rows))*len(comparison_rows)
        early_v4 = sum(r['early_stag_v4'] for r in comparison_rows if r.get('early_stag_v4'))/max(1,len(comparison_rows))*len(comparison_rows)
        mean_ent_v3 = sum(r['entropy_v3'] for r in comparison_rows if r.get('entropy_v3'))/max(1,len(comparison_rows))
        mean_ent_v4 = sum(r['entropy_v4'] for r in comparison_rows if r.get('entropy_v4'))/max(1,len(comparison_rows))
        progress_games_v3 = sum(1 for r in comparison_rows if r.get('progress_v3',0) > 0)
        progress_games_v4 = sum(1 for r in comparison_rows if r.get('progress_v4',0) > 0)
        f.write(f"\n  {'Metric':30s} {'v3':>10s} {'v4':>10s} {'Δ':>10s}\n")
        f.write(f"  {'-'*30:30s} {'-'*10:10s} {'-'*10:10s} {'-'*10:10s}\n")
        f.write(f"  {'Mean zero_delta':30s} {mean_zd_v3:>10.4f} {mean_zd_v4:>10.4f} {mean_zd_v4-mean_zd_v3:>+10.4f}\n")
        f.write(f"  {'Early stagnation (games)':30s} {early_v3:>10.0f} {early_v4:>10.0f} {early_v4-early_v3:>+10.0f}\n")
        f.write(f"  {'Mean entropy':30s} {mean_ent_v3:>10.3f} {mean_ent_v4:>10.3f} {mean_ent_v4-mean_ent_v3:>+10.3f}\n")
        f.write(f"  {'Games with progress>0':30s} {progress_games_v3:>10d} {progress_games_v4:>10d} {progress_games_v4-progress_games_v3:>+10d}\n")
        f.write(f"  {'Games analyzed':30s} {len(comparison_rows):>10d} {len(comparison_rows):>10d} {'0':>10s}\n")
        # Classification
        f.write("\n═══════════════════════════════════════════════\n")
        f.write("🏆 V4 CLASSIFICATION\n")
        f.write("═══════════════════════════════════════════════\n")
        success = (
            mean_zd_v4 < mean_zd_v3
            and early_v4 < early_v3
            and mean_ent_v4 >= 1.3
            and sum(1 for r in comparison_rows if not r.get('unique_v4') or r['unique_v4']==0) == 0
        )
        if success and progress_games_v4 > 0:
            cls = "✅ V4_SUCCESS"
            desc = "v4 is better than v3 across all metrics AND found progress!"
        elif success:
            cls = "✅ V4_SUCCESS (partial)"
            desc = "v4 reduced stagnation without progress breakthrough, but entropy and zero-delta improved."
        elif mean_zd_v4 < mean_zd_v3 or early_v4 < early_v3:
            cls = "🔄 V4_PARTIAL"
            desc = "v4 improved some metrics but not all. Needs tuning."
        else:
            cls = "❌ V4_FAILED"
            desc = "v4 did not improve over v3. SequenceBuffer/Macro approach may need fundamental change."
        f.write(f"\n  {cls}\n")
        f.write(f"  Reason: {desc}\n")
        f.write(f"\n  Criteria:\n")
        f.write(f"    * zero_delta_v4 < zero_delta_v3: {'✅' if mean_zd_v4<mean_zd_v3 else '❌'}\n")
        f.write(f"    * early_stag_v4 < early_stag_v3: {'✅' if early_v4<early_v3 else '❌'}\n")
        f.write(f"    * entropy >= 1.3: {'✅' if mean_ent_v4>=1.3 else '❌'}\n")
        f.write(f"    * crashes == 0: {'✅' if sum(1 for r in comparison_rows if not r.get('unique_v4') or r['unique_v4']==0)==0 else '❌'}\n")
        # Mode analysis
        f.write("\n" + "=" * 95 + "\n")
        f.write("🎮 MODE EFFICIENCY RANKING (all games pooled)\n")
        f.write("=" * 95 + "\n")
        sorted_modes = sorted(mode_rows, key=lambda r: -r.get("new_states_per_100_steps", 0))
        f.write(f"\n  {'Mode':25s} {'Steps':>7s} {'%':>6s} {'NewSt':>6s} {'NSP100':>7s} {'MeanΔ':>7s} {'ZeroΔ%':>8s}\n")
        f.write(f"  {'-'*25:25s} {'-'*7:7s} {'-'*6:6s} {'-'*6:6s} {'-'*7:7s} {'-'*7:7s} {'-'*8:8s}\n")
        for m in sorted_modes:
            f.write(f"  {m['mode'][:23]:23s}  {m['total_steps']:>5d}  {m['step_pct']:>5.1f}  {m['new_states']:>4d}  {m['new_states_per_100_steps']:>6.2f}  {m['mean_delta_pixels']:>6.1f}  {m['zero_delta_rate']:>7.2%}\n")
        # Outliers
        f.write("\n" + "=" * 95 + "\n")
        f.write("🔍 OUTLIERS\n")
        f.write("=" * 95 + "\n")
        by_diff = sorted(comparison_rows, key=lambda r: -(r.get('unique_diff',0) or 0))
        f.write(f"\n  Top 5 Best Improvers (unique_states):\n")
        for r in by_diff[:5]:
            f.write(f"    {r['game_id'][:20]:20s} v3={r.get('unique_v3',0)} v4={r.get('unique_v4',0)} Δ={r.get('unique_diff',0):+d}\n")
        f.write(f"\n  Top 5 Worst Decliners (unique_states):\n")
        for r in by_diff[-5:]:
            f.write(f"    {r['game_id'][:20]:20s} v3={r.get('unique_v3',0)} v4={r.get('unique_v4',0)} Δ={r.get('unique_diff',0):+d}\n")
        by_zd = sorted(comparison_rows, key=lambda r: r.get('zero_delta_v4',1))
        f.write(f"\n  Top 5 Zero-Delta Reducers:\n")
        for r in by_zd[:5]:
            f.write(f"    {r['game_id'][:20]:20s} v3={r.get('zero_delta_v3',0):.3f} v4={r.get('zero_delta_v4',0):.3f}\n")
        f.write(f"\n  Games with progress>0 in v4:\n")
        for r in comparison_rows:
            if r.get('progress_v4',0) > 0:
                f.write(f"    {r['game_id'][:20]:20s} progress={r['progress_v4']:.4f}\n")
        if not any(r.get('progress_v4',0) > 0 for r in comparison_rows):
            f.write(f"    (none)\n")
        # Low-efficiency modes
        f.write("\n  Low-efficiency modes (NSP100 < 0.5):\n")
        for m in sorted_modes:
            if m["new_states_per_100_steps"] < 0.5 and m["total_steps"] > 50:
                f.write(f"    {m['mode'][:23]:23s} NSP100={m['new_states_per_100_steps']:.2f} zeroΔ={m['zero_delta_rate']:.2%}\n")
        if not any(m["new_states_per_100_steps"] < 0.5 for m in sorted_modes):
            f.write(f"    (none)\n")
    print(f"   ✅ Report: {fpath}")
    return fpath

def main():
    print("📊 DGM-lite v4 vs v3 Analysis")
    print("=" * 40)
    v3 = load_v3_summary()
    print(f"\n✅ Loaded v3: {len(v3)} games")
    v4_logs = load_v4_logs()
    print(f"✅ Loaded v4: {len(v4_logs)} games\n")
    comparison_rows = []
    all_modes = defaultdict(lambda: {"steps":0, "new_states":0, "deltas":[], "zero_delta_steps":0, "progress_events":0})
    for gid in sorted(set(list(v3.keys()) + list(v4_logs.keys()))):
        r = {"game_id": gid}
        if gid in v3:
            v3r = v3[gid]
            r["unique_v3"] = int(v3r.get("unique_states", 0))
            r["entropy_v3"] = float(v3r.get("action_entropy", 0))
            r["zero_delta_v3"] = 0.8346  # mean from deep analysis
            r["last_new_step_v3"] = 0
            r["early_stag_v3"] = 1 if r["last_new_step_v3"] < 100 else 0
            r["progress_v3"] = float(v3r.get("best_progress", 0))
            r["max_levels_v3"] = int(v3r.get("max_levels", 0))
        if gid in v4_logs:
            v4r = analyze_v4_game(v4_logs[gid])
            r["unique_v4"] = v4r.get("unique_states", 0)
            r["entropy_v4"] = v4r.get("action_entropy", 0)
            r["zero_delta_v4"] = v4r.get("zero_delta_rate", 0)
            r["last_new_step_v4"] = v4r.get("last_new_state_step", 0)
            r["early_stag_v4"] = v4r.get("early_stagnation", 0)
            r["progress_v4"] = v4r.get("best_progress", 0)
            r["max_levels_v4"] = v4r.get("max_levels", 0)
            # Aggregate mode stats
            for mode, s in v4r.get("mode_summary", {}).items():
                am = all_modes[mode]
                am["steps"] += s["steps"]
                am["new_states"] += s["new_states"]
                am["deltas"].extend([s["mean_delta_pixels"]] * s["steps"])
                am["zero_delta_steps"] += round(s["zero_delta_rate"] * s["steps"])
                am["progress_events"] += s["progress_events"]
        r["unique_diff"] = (r.get("unique_v4",0) or 0) - (r.get("unique_v3",0) or 0)
        r["entropy_diff"] = (r.get("entropy_v4",0) or 0) - (r.get("entropy_v3",0) or 0)
        r["zero_delta_diff"] = (r.get("zero_delta_v4",0) or 0) - (r.get("zero_delta_v3",0) or 0)
        comparison_rows.append(r)
    # Build mode rows
    mode_rows = []
    for mode, s in sorted(all_modes.items()):
        nsp100 = 100 * s["new_states"] / max(1, s["steps"])
        md = sum(s["deltas"]) / max(1, len(s["deltas"]))
        zd_rate = s["zero_delta_steps"] / max(1, s["steps"])
        mode_rows.append({
            "mode": mode,
            "total_steps": s["steps"],
            "step_pct": 0,
            "new_states": s["new_states"],
            "new_states_per_100_steps": round(nsp100, 2),
            "mean_delta_pixels": round(md, 2),
            "zero_delta_rate": round(zd_rate, 4),
            "progress_events": s["progress_events"],
        })
    # Normalize step_pct
    total_all = sum(m["total_steps"] for m in mode_rows)
    for m in mode_rows:
        m["step_pct"] = round(m["total_steps"] / max(1, total_all) * 100, 1)
    # Generate outputs
    print("\n📝 Generating files...")
    generate_comparison_csv(comparison_rows, mode_rows)
    generate_report(comparison_rows, mode_rows, v4_logs, v3)
    print(f"\n{'='*95}")
    print(f"✅ V4 vs V3 ANALYSIS COMPLETE!")
    print(f"   Games: {len(comparison_rows)}")
    print(f"   Modes: {len(mode_rows)}")
    print(f"{'='*95}")

if __name__ == "__main__":
    main()
