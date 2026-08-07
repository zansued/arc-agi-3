"""
V62 — Pure Symbolic Deduction Solver for ARC-AGI-3

Strategy: Read game mechanics directly from class definition,
plan actions symbolically based on sprite tags and level data.
No brute-force BFS, no ML, no alucinações.
"""
import importlib.util
import sys
import os
from pathlib import Path

GAMES_DIR = Path("/a0/usr/workdir/environment_files")

def load_game_class(game_id: str):
    """Dynamic load a game class from its .py file."""
    game_dir = GAMES_DIR / game_id
    if not game_dir.exists():
        raise FileNotFoundError(f"Game {game_id} not found in {GAMES_DIR}")
    
    subdirs = list(game_dir.iterdir())
    if not subdirs:
        raise FileNotFoundError(f"No subdirectory for game {game_id}")
    
    py_file = subdirs[0] / f"{game_id}.py"
    if not py_file.exists():
        raise FileNotFoundError(f"Game file not found: {py_file}")
    
    # Load the module
    spec = importlib.util.spec_from_file_location(game_id, py_file)
    module = importlib.util.module_from_spec(spec)
    
    # Find the ARCBaseGame subclass
    old_classes = set(sys.modules.keys())
    spec.loader.exec_module(module)
    
    for name, obj in module.__dict__.items():
        if isinstance(obj, type) and hasattr(obj, '__bases__'):
            for base in obj.__bases__:
                if 'ARCBaseGame' in str(base):
                    return obj
    
    raise ValueError(f"No ARCBaseGame subclass found in {py_file}")


def inspect_game(game_id: str) -> dict:
    """Inspect game class to extract symbolic information."""
    game_class = load_game_class(game_id)
    
    # Instantiate to inspect
    game = game_class()
    
    info = {
        'game_id': game.game_id,
        'available_actions': game._ARCBaseGame__dict__.get('_available_actions', game._available_actions),
        'num_levels': len(game._levels),
        'win_score': game.win_score,
    }
    
    # Inspect current level
    level = game.current_level
    info['grid_size'] = level.grid_size
    
    # Get all unique tags
    tags = level.get_all_tags()
    info['sprite_tags'] = sorted(list(tags))
    
    # Count sprites per tag
    tag_counts = {}
    for tag in tags:
        sprites = level.get_sprites_by_tag(tag)
        tag_counts[tag] = len(sprites)
    info['tag_counts'] = tag_counts
    
    # Get level data
    level_data = {}
    if hasattr(level, '_data'):
        level_data = dict(level._data)
    info['level_data'] = level_data
    
    # Get all sprites with positions
    all_sprites = level.get_sprites()
    sprite_info = []
    for s in all_sprites:
        sprite_info.append({
            'name': s.name,
            'position': (s.x, s.y),
            'tags': s.tags,
            'visible': s.is_visible,
            'collidable': s.is_collidable,
            'scale': s.scale,
            'rotation': s.rotation,
            'layer': s.layer,
        })
    info['sprites'] = sprite_info
    info['sprite_count'] = len(all_sprites)
    
    return info


def categorize_game(info: dict) -> str:
    """Determine game category based on actions and sprite tags."""
    actions = info['available_actions']
    num_actions = len(actions)
    tags = info['sprite_tags']
    tag_counts = info['tag_counts']
    
    # Category logic based on action set
    if num_actions == 0:
        return 'E_AUTO'  # Automatic / turn-based
    elif set(actions) == {6}:
        return 'C_CLICK'  # Click-only
    elif set(actions) == {1, 2, 3, 4}:
        return 'A_NAV'  # Pure navigation
    elif set(actions) == {6, 7}:
        return 'D_CLICK_PLUS'  # Click + special action
    elif set(actions) == {5, 6, 7}:
        return 'D_SIMULATION'  # Simulation with 3 special actions
    elif set(actions) == {1, 2, 3, 4, 5}:
        return 'B_NAV_ACTION'  # Navigation + action5
    elif set(actions) == {1, 2, 3, 4, 6}:
        return 'B_NAV_CLICK'  # Navigation + click
    elif set(actions) in [{1,2,3,4,5,6}, {1,2,3,4,6,7}]:
        if 'sys_click' in tags:
            return 'B_COMPLEX'  # Complex with clickable sprites
        elif info['grid_size'] and max(info['grid_size']) <= 16:
            return 'B_PAINT'  # Small grid = sprite manipulation (like sp80)
        else:
            return 'B_COMPLEX'
    elif set(actions) == {1,2,3,4,5,6,7}:
        return 'D_FULL'  # All 7
    else:
        return 'UNKNOWN'


if __name__ == "__main__":
    # Test on sp80 (known painting game)
    print("=" * 60)
    print("🔍 INSPECTING sp80 (Known Painting Game)")
    print("=" * 60)
    info = inspect_game("sp80")
    print(f"Actions: {info['available_actions']}")
    print(f"Grid: {info['grid_size']}")
    print(f"Levels: {info['num_levels']}")
    print(f"Tags ({len(info['sprite_tags'])}): {info['sprite_tags'][:10]}...")
    print(f"Tag counts: {dict(list(info['tag_counts'].items())[:15])}")
    print(f"Level data: {info['level_data']}")
    print(f"Sprite count: {info['sprite_count']}")
    cat = categorize_game(info)
    print(f"Category: {cat}")
    
    print()
    print("=" * 60)
    print("🔍 INSPECTING ls20 (Navigation Game)")
    print("=" * 60)
    info = inspect_game("ls20")
    print(f"Actions: {info['available_actions']}")
    print(f"Grid: {info['grid_size']}")
    print(f"Levels: {info['num_levels']}")
    print(f"Tags ({len(info['sprite_tags'])}): {info['sprite_tags'][:10]}")
    print(f"Tag counts: {dict(list(info['tag_counts'].items())[:15])}")
    print(f"Level data: {info['level_data']}")
    print(f"Sprite count: {info['sprite_count']}")
    cat = categorize_game(info)
    print(f"Category: {cat}")
    
    print()
    print("=" * 60)
    print("🔍 INSPECTING m0r0 (Small Grid, Complex)")
    print("=" * 60)
    info = inspect_game("m0r0")
    print(f"Actions: {info['available_actions']}")
    print(f"Grid: {info['grid_size']}")
    print(f"Levels: {info['num_levels']}")
    print(f"Tags ({len(info['sprite_tags'])}): {info['sprite_tags']}")
    print(f"Tag counts: {dict(info['tag_counts'])}")
    print(f"Level data: {info['level_data']}")
    print(f"Sprite count: {info['sprite_count']}")
    cat = categorize_game(info)
    print(f"Category: {cat}")
