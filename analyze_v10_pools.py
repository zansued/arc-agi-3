import os, json

arc_dir = os.path.expanduser("arc_runs")

improved = ["sp80", "bp35", "sc25", "ls20", "cd82"]
regressed = ["lf52", "g50t", "sk48", "m0r0"]

results = {}
for game in improved + regressed:
    fpath = os.path.join(arc_dir, f"v10_{game}.jsonl")
    if not os.path.exists(fpath):
        results[game] = {"error": "no file"}
        continue
    with open(fpath) as f:
        lines = f.readlines()
    frontier = depth = fallback = 0
    explore_count = 0
    archive_selects = 0
    max_pixels = 0
    progress_step = 0
    final_states = 0
    for line in lines:
        try:
            entry = json.loads(line)
        except:
            continue
        sel = entry.get("archive_selector", "")
        if sel == "frontier_pool":
            frontier += 1
        elif sel == "depth_pool":
            depth += 1
        elif sel in ("general_pool", "v9_all"):
            fallback += 1
        if sel and sel != "none":
            archive_selects += 1
        if entry.get("mode") == "EXPLORE_FROM_CELL":
            explore_count += 1
        pixels = entry.get("changed_pixels", 0)
        if isinstance(pixels, (int, float)) and pixels > max_pixels:
            max_pixels = pixels
        levels = entry.get("levels_completed", 0)
        if isinstance(levels, (int, float)) and levels > 0 and progress_step == 0:
            progress_step = entry.get("step", 0)
        final_states = entry.get("unique_states", final_states)
    total_sel = frontier + depth + fallback
    frontier_pct = round(frontier / total_sel * 100, 1) if total_sel else 0
    depth_pct = round(depth / total_sel * 100, 1) if total_sel else 0
    results[game] = {
        "states": final_states,
        "frontier": frontier, "depth": depth, "fallback": fallback,
        "frontier_pct": frontier_pct, "depth_pct": depth_pct,
        "archive_selects": archive_selects,
        "explore_from_cell": explore_count,
        "max_pixels": max_pixels, "progress_step": progress_step
    }

print("=== V10A FRONTIER vs DEPTH ANALYSIS ===")
print()
for group, games in [("IMPROVED (vs v9)", improved), ("REGRESSED (vs v9)", regressed)]:
    print(f"--- {group} ---")
    print("Game     States   Fron Depth  Fal    F%    D% ExpFC  MxPx   Prg")
    for g in games:
        r = results.get(g, {})
        s = r.get("states","?")
        f = r.get("frontier","?")
        d = r.get("depth","?")
        fb = r.get("fallback","?")
        fp = r.get("frontier_pct","?")
        dp = r.get("depth_pct","?")
        ec = r.get("explore_from_cell","?")
        mp = r.get("max_pixels","?")
        pg = r.get("progress_step",0)
        print(f"{g:<8} {str(s):>5} {str(f):>5} {str(d):>5} {str(fb):>4} {str(fp):>5} {str(dp):>5} {str(ec):>5} {str(mp):>5} {str(pg):>4}")
    print()

print("=== DOMINANCE PATTERN ===")
for g in improved + regressed:
    r = results.get(g, {})
    if "frontier_pct" not in r:
        continue
    fp, dp = r["frontier_pct"], r["depth_pct"]
    if fp > 60:
        dom = "frontier-dominated"
    elif dp > 60:
        dom = "depth-dominated"
    else:
        dom = "balanced"
    print(f"{g}: {dom} ({fp:.0f}% frontier / {dp:.0f}% depth)")
