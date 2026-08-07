#!/usr/bin/env python3
"""inspect_step_api.py — Inspeciona FrameDataRaw e retorno de step() em jogos sentinelas"""
import os, json, sys
from datetime import datetime
import numpy as np
from arc_agi import Arcade
from arcengine import GameAction

TARGET_GAMES = ["sk48", "tn36", "bp35"]
STEPS = 20
OUT_DIR = "arc_runs"
os.makedirs(OUT_DIR, exist_ok=True)

def inspect(obj, name, depth=0):
    if depth > 2 or obj is None:
        return f"{'  '*depth}{name}: {type(obj).__name__ if obj is not None else 'None'}\n"
    if isinstance(obj, (int, float, bool, str, bytes)):
        return f"{'  '*depth}{name}: {obj!r}\n"
    if isinstance(obj, (list, tuple)):
        line = f"{'  '*depth}{name}: {type(obj).__name__}[{len(obj)}]\n"
        for i, item in enumerate(obj[:6]):
            if isinstance(item, (int, float, str)):
                line += f"{'  '*(depth+1)}[{i}]: {item!r}\n"
            else:
                line += inspect(item, f"[{i}]", depth+1)
        if len(obj) > 6:
            line += f"{'  '*(depth+1)}... +{len(obj)-6} more\n"
        return line
    if isinstance(obj, np.ndarray):
        return f"{'  '*depth}{name}: ndarray shape={obj.shape} dtype={obj.dtype}\n"
    if hasattr(obj, '__dict__'):
        line = f"{'  '*depth}{name}: {type(obj).__name__} (__dict__)\n"
        for k, v in sorted(obj.__dict__.items()):
            if k.startswith('_'): continue
            line += inspect(v, f".{k}", depth+1)
        return line
    attrs = []
    try:
        for a in dir(obj):
            if not a.startswith('_'):
                try:
                    v = getattr(obj, a)
                    if not callable(v):
                        attrs.append(a)
                except: pass
    except: pass
    if attrs:
        line = f"{'  '*depth}{name}: {type(obj).__name__}\n"
        for a in attrs[:25]:
            try:
                v = getattr(obj, a)
                line += f"{'  '*(depth+1)}.{a}: {type(v).__name__}"
                if isinstance(v, (int, float, bool, str)):
                    line += f" = {v!r}"
                line += "\n"
            except: pass
        return line
    return f"{'  '*depth}{name}: {type(obj).__name__}\n"

def run_inspection(gid):
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"INSPECTION: Game = {gid}")
    lines.append('='*70)
    game = Arcade().make(gid)
    try: game.reset()
    except Exception as e: lines.append(f"Reset error: {e}")
    import time as _t
    _t.sleep(0.2)
    raw = getattr(game, "observation_space", None)
    lines.append(f"\n--- observation_space (FrameDataRaw) ---")
    lines.append(inspect(raw, "obs"))
    lines.append(f"\n--- STEP INSPECTION ({STEPS} steps) ---")
    for step in range(STEPS):
        avail = []
        if raw is not None and hasattr(raw, "available_actions"):
            aa = raw.available_actions
            if aa is not None and len(aa) > 0: avail = list(aa)
        if not avail: avail = [0, 1, 2, 3, 4, 5, 6, 7]
        action_val = avail[0] if avail else 0
        if isinstance(action_val, int):
            step_action = GameAction.from_id(action_val) if action_val != 6 else GameAction.ACTION6
            step_data = {"x": 32, "y": 32} if action_val == 6 else None
        else:
            name = getattr(action_val, "name", str(action_val))
            step_action = action_val
            step_data = {"x": 32, "y": 32} if name == "ACTION6" else None
        before_frame = None
        if raw is not None and hasattr(raw, "frame"):
            try:
                before_frame = np.asarray(raw.frame, dtype=np.int32)
                if before_frame.ndim == 3: before_frame = before_frame[0]
            except: pass
        try:
            if step_data: result = game.step(step_action, data=step_data)
            else: result = game.step(step_action)
        except Exception as e:
            lines.append(f"  Step {step}: action={action_val} -> ERROR: {e}")
            continue
        lines.append(f"\n  --- Step {step}: action={action_val} ---")
        lines.append(f"  Result type: {type(result).__name__}")
        if isinstance(result, tuple):
            lines.append(f"  Result tuple length: {len(result)}")
            for i, part in enumerate(result):
                if isinstance(part, (int, float, bool)):
                    lines.append(f"    [{i}]: {part!r}")
                elif isinstance(part, str):
                    lines.append(f"    [{i}]: str len={len(part)}")
                elif isinstance(part, np.ndarray):
                    lines.append(f"    [{i}]: ndarray shape={part.shape}")
                elif part is None:
                    lines.append(f"    [{i}]: None")
                elif isinstance(part, dict):
                    lines.append(f"    [{i}]: dict with {len(part)} keys")
                    for k, v in part.items():
                        lines.append(f"      .{k} = {v!r}")
                else:
                    lines.append(f"    [{i}]: {type(part).__name__}")
        new_raw = getattr(game, "observation_space", None)
        after_frame = None
        if new_raw is not None and hasattr(new_raw, "frame"):
            try:
                after_frame = np.asarray(new_raw.frame, dtype=np.int32)
                if after_frame.ndim == 3: after_frame = after_frame[0]
                if before_frame is not None:
                    changed = int(np.sum(before_frame != after_frame))
                    lines.append(f"  Changed pixels: {changed}")
            except: pass
        score_fields = ["score","reward","state","level","levels_completed",
                        "win_levels","game_state","won","terminated","truncated",
                        "status","done","solved"]
        found = []
        if isinstance(result, tuple):
            for i, part in enumerate(result):
                if isinstance(part, dict):
                    for k in score_fields:
                        if k in part: found.append(f"result[{i}].{k}={part[k]!r}")
                elif hasattr(part, '__dict__'):
                    d = part.__dict__
                    for k in score_fields:
                        if k in d: found.append(f"result[{i}].{k}={d[k]!r}")
        if new_raw is not None:
            for k in score_fields:
                if hasattr(new_raw, k):
                    v = getattr(new_raw, k)
                    if v is not None: found.append(f"obs.{k}={v!r}")
        if found:
            lines.append(f"  >>> PROGRESS: {found[0]}")
            for fp in found[1:]:
                lines.append(f"             {fp}")
        else:
            lines.append(f"  (no score/progress field in step result)")
        raw = new_raw
        if step >= 4: break
    content = "\n".join(lines)
    fpath = os.path.join(OUT_DIR, f"inspect_{gid}.md")
    with open(fpath, "w") as f: f.write(content)
    print(f"Saved: {fpath}")
    print(content)

def main():
    print("="*70)
    print("   ARC-AGI-3: Step API Inspection (score/progress real)")
    print("="*70)
    print(f"Target: {TARGET_GAMES}")
    print(f"Time: {datetime.now().strftime('%H:%M')}")
    for gid in TARGET_GAMES:
        try: run_inspection(gid)
        except Exception as e:
            import traceback
            print(f"\nERROR {gid}: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
