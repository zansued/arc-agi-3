#!/usr/bin/env python3
"""Testar LocalEnvironmentWrapper em varios jogos."""
import warnings, logging, uuid
warnings.filterwarnings('ignore')
from arc_agi import Arcade
from arc_agi.local_wrapper import LocalEnvironmentWrapper

a = Arcade()
envs = a.get_environments()
logger = logging.getLogger('test')

targets = ['tn36', 'sp80', 'bp35', 'cn04', 'cd82', 'sk48', 'vc33', 'wa30']
for target in targets:
    matches = [e for e in envs if target in e.game_id]
    if not matches:
        print(f"{target}: NOT FOUND")
        continue
    e = matches[0]
    ba = [int(x) for x in e.baseline_actions]
    print(f"\n--- {e.game_id} ---")
    print(f"  Baseline: {ba[:5]}...")

    try:
        wrapper = LocalEnvironmentWrapper(e, logger, str(uuid.uuid4()))
        print(f"  Action space: {wrapper.action_space}")

        for ba_val in e.baseline_actions[:5]:
            wrapper.reset()
            try:
                obs = wrapper.step(ba_val)
                print(f"  step({int(ba_val)}): levels={obs.levels_completed} state={obs.state}")
            except Exception as ex:
                print(f"  step({int(ba_val)}): ERROR - {str(ex)[:100]}")
    except Exception as ex:
        print(f"  WRAPPER ERROR: {str(ex)[:200]}")
