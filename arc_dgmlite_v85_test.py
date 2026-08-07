#!/usr/bin/env python3
"""Quick test for v8.5 fix - runs 50 steps on bp35"""
import sys, os, json
sys.path.insert(0, '/a0/usr/workdir')

# Force import from local file
import importlib.util
spec = importlib.util.spec_from_file_location("v85", "/a0/usr/workdir/arc_dgmlite_v85_causal_object.py")
v85 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v85)

l, s = v85.run_game("bp35-0a0ad940", max_steps=50)

states = len(set(e.get("state_hash", "") for e in l if e.get("state_hash")))
zd = sum(1 for e in l if e.get("changed_pixels", 0) == 0)

print(f"TEST_OK: {len(l)} steps, {states} states, {zd} zero_delta, status={s}")

out = os.path.join(v85.OUT_DIR, "v85_bp35-test.jsonl")
with open(out, 'w') as f:
    for entry in l:
        f.write(json.dumps(entry) + '\n')
print(f"Written to {out}")
