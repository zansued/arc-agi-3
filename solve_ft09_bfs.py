#!/usr/bin/env python3
"""
ft09 BFS Solver

ft09 mechanics:
- Camera(0,0,16,16,4,4) → display coords 0..63, grid coords 0..15.75
- display_to_grid(display_x, display_y) → (grid_x, grid_y)
- Sprite position (x,y) is in grid coordinates (pixel units)
- Click center of tile at (sprite.x*4+2, sprite.y*4+2) in display coords
- Click cycles tile color through gqb palette
- For elp pattern: only elp[j][i]==1 positions modify neighbor tiles
- Win condition cgj: each bsT sprite checked against neighbor Hkx
"""
import sys
sys.path.insert(0, '/a0/usr/workdir')
from arcengine import ActionInput, GameAction, GameState
import importlib.util
import os
from pathlib import Path
from itertools import product
import json
import time

GAMES_DIR = Path("/a0/usr/workdir/environment_files")

def load_game_class(game_id):
    game_dir = GAMES_DIR / game_id
    subdirs = list(game_dir.iterdir())
    py_file = subdirs[0] / f"{game_id}.py"
    spec = importlib.util.spec_from_file_location(game_id, py_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, obj in module.__dict__.items():
        if isinstance(obj, type) and hasattr(obj, '__bases__'):
            for base in obj.__bases__:
                if 'ARCBaseGame' in str(base):
                    return obj
    raise ValueError(f"No ARCBaseGame subclass in {py_file}")


def make_click(tile_sprite):
    """Click center of a tile in display coordinates."""
    # Camera: 4 pixels per grid unit, starting at (0,0)
    # Sprite position (x,y) in grid units
    # Center of sprite in display: (x*4 + width*4/2, y*4 + height*4/2)
    # But for Hkx (3x3 pixels at 1x scale), width=3, height=3
    # So center in display coords: x*4 + 3*4/2 = x*4 + 6 if scale=4? No...
    
    # Actually sprite pixels don't use the grid spacing directly.
    # sprite.x and sprite.y are in the game's pixel grid (same as grid coords)
    # Camera converts: display pixel → grid coord
    # If camera has 4 px/grid, then display_x maps to grid_x/4
    # So to click on sprite at (sx, sy), display coords = sx*4 + 2, sy*4 + 2
    
    # Wait, let me check: display_to_grid(x,y) returns (grid_x, grid_y)
    # Looking at step(): Hzf = self.camera.display_to_grid(AfP, Ywt)
    # Then ppb, tut = Hzf
    # Then Wmr = self.current_level.get_sprite_at(ppb, tut, "Hkx")
    # So display_to_grid returns grid coordinates where sprites live
    
    # Hkx sprite at (x=10, y=7) → center in display = (10*4 + 1.5*4, ?) = (46, ?)
    # Hmm, but sprite dimensions are in pixels, not grid units.
    # The get_sprite_at uses grid coords directly.
    # 
    # Actually looking more carefully at line 2415:
    # cAw = (self.blr.x + (ybc * 4), self.blr.y + (lga * 4))
    # This means sprite coordinates are in a pixel grid where spacing is 4.
    # So display_to_grid(display_x, display_y) probably returns something
    # that corresponds to the sprite coordinate system.
    #
    # For the camera at (0,0,16,16,4,4):
    # grid_x = display_x / 4 (approximately rounded)
    # So display at 42 → grid 10.5 → get_sprite_at(10, 10) finds sprite at (10, 10) if tile is 3-wide
    
    # Simple approach: click at display coords that map to the sprite position
    # For sprite at (sx, sy), click at display coords (sx*4 + 2, sy*4 + 2)?
    # Or maybe sx*4 + 1 and sy*4 + 1?
    
    # Actually, looking at the camera constructor:
    # Camera(0, 0, 16, 16, 4, 4, interfaces)
    # 0,0 = camera position in game world
    # 16,16 = viewport size in game units
    # 4,4 = pixels per game unit
    
    # So to convert: display_to_grid(dx, dy) → (dx/4 + cam_x, dy/4 + cam_y)
    # cam_x=0, cam_y=0, so grid_x = dx/4, grid_y = dy/4
    
    # To target sprite at (sx, sy): grid should be close to (sx, sy)
    # display_x = sx * 4, display_y = sy * 4
    # To hit center of 3-pixel-wide sprite: sx*4 + 1.5 → but display uses int
    # sx*4 + 1 might work since the camera maps pixels to grid
    
    sx, sy = tile_sprite.x, tile_sprite.y
    # Tile center in sprite coords: +1 for half of 3-pixel width
    # But display_to_grid maps display px to grid
    # If sprite is at (10,7) and width 3, its pixels cover cols 10,11,12
    # Center is at 11 → display 11*4 + 2 = 46? No...
    # 
    # I think the simplest is: display at sx*4 + 2 should map to around sx+0.5
    # Let's use (sx*4 + 2, sy*4 + 2)
    return ActionInput(id=GameAction.ACTION6, data={'x': sx * 4 + 2, 'y': sy * 4 + 2})


def test_level0():
    """Test ft09 level 0 by trying to click on all Hkx tiles."""
    print("=" * 50)
    print("FT09 Level 0 Test")
    print("=" * 50)
    
    GameClass = load_game_class('ft09')
    game = GameClass()
    
    print(f"Number of levels: {len(game._levels)}")
    print(f"Current level: {game.level_index}")
    
    # Get Hkx and bsT
    hkx_sprites = game.current_level.get_sprites_by_tag("Hkx")
    bst_sprites = game.current_level.get_sprites_by_tag("bsT")
    
    print(f"\nHkx tiles: {len(hkx_sprites)}")
    for s in hkx_sprites:
        center_color = s.pixels[1][1]
        print(f"  {s.name} at ({s.x}, {s.y}) center={center_color}")
    
    print(f"\nbsT targets: {len(bst_sprites)}")
    for s in bst_sprites:
        center_color = s.pixels[1][1]
        flag = s.pixels[0][0]
        print(f"  {s.name} at ({s.x}, {s.y}) center={center_color} flag={flag}")
    
    # Get level data
    level_data = {}
    if hasattr(game.current_level, '_data'):
        level_data = dict(game.current_level._data)
    print(f"\nLevel data: {level_data}")
    
    # gqb palette
    gqb = game.gqb if hasattr(game, 'gqb') else level_data.get('cwU', [9, 8])
    print(f"Palette (gqb): {gqb}")
    
    # Test click on each tile
    print("\nTesting clicks...")
    for s in hkx_sprites[:3]:
        action = make_click(s)
        print(f"  Click on {s.name} at ({s.x},{s.y}): action=({action.data['x']},{action.data['y']})")
        
        # Get color before
        before = s.pixels[1][1]
        
        frame = game.perform_action(action)
        
        # Get color after
        after = s.pixels[1][1]
        
        print(f"    Color: {before} → {after}, state={frame.state if frame else 'NONE'}")
        
        if frame and frame.state == GameState.WIN:
            print(f"    🎉 WIN!")
    
    print("\n✅ Test complete")


if __name__ == '__main__':
    test_level0()
