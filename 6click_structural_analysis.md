# CLICK Game Structural Analysis — 6 Games for ARC-AGI-3 Symbolic Solver

## 1. ft09 — Color Tile Cycling

### Source
- File: `environment_files/ft09/0d8bbf25/ft09.py` (2520 lines)
- Class: `Ft09` (line 2301)
- Available actions: `[6]` (CLICK)

### __init__ (line 2302)
~~~python
def __init__(self) -> None:
    ZnK = levels[0].get_data("kCv") if levels else 0
    bUg = ZnK if ZnK else 0
    self.lpw = sve(bUg, self)  # sve = RenderableUserDisplay (step counter)
    super().__init__("ft09", levels, Camera(0, 0, 16, 16, 4, 4, [self.lpw]), available_actions=[6])
~~~
- Camera: 16x16 viewport, 4px spacing, grid determined per level
- Step counter `sve` reads counter from `kCv` level data

### on_set_level (line 2314)
~~~python
def on_set_level(self, level: Level) -> None:
    self.olv()  # update step counter
    self.zth = None
    self.our = 0
    if self.level_index == 0:
        Uev = self.current_level.get_sprites_by_tag("Ycb")
        if Uev: self.zth = Uev[0]  # special tutor sprite for level 0
    rKu = self.current_level.grid_size
    self.pdw = rKu[0]; self.zbh = rKu[1]
    self.gig = self.current_level.get_sprites_by_tag("bsT")  # TARGETS
    self.fhc = self.current_level.get_sprites_by_tag("Hkx")   # CLICKABLE TILES
    self.mou = self.current_level.get_sprites_by_tag("NTi")   # INACTIVE TILES
    self.gqb = self.current_level.get_data("cwU")             # PALETTE
    if self.gqb is None: self.gqb = [9, 8]
    self.irw = self.current_level.get_data("elp")             # PATTERN (3x3 mask)
    if self.irw is None: self.irw = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
    # Initialize all Hkx tiles to first palette color
    for rmy, zge in enumerate(self.fhc):
        zge.color_remap(zge.pixels[0][0], self.gqb[0])
    # Also set NTi tiles to first palette color (keeping 6 as blank)
    for rmy, zge in enumerate(self.mou):
        for jon in range(3):
            for vlo in range(3):
                if zge.pixels[jon][vlo] != 6:
                    zge.pixels[jon][vlo] = self.gqb[0]
~~~

### step (line 2350) — Main Action Loop
~~~python
def step(self) -> None:
    if self.action.id.value == 0:  # NOOP
        self.complete_action(); return
    # Level 0 tutor: sprite blinks for 4 steps
    if self.our > 0 and self.zth:
        self.our -= 1
        aIT = 0 if self.our % 2 == 1 else 2
        Ytt = self.zth.pixels > -1
        self.zth.pixels[Ytt] = aIT
        if self.our == 0: self.complete_action()
        return
    kMO = None; ATn = False; Hzf = None
    if self.action.id.value == 6:  # CLICK
        AfP = self.action.data.get("x", 0)
        Ywt = self.action.data.get("y", 0)
        Hzf = self.camera.display_to_grid(AfP, Ywt)
        if Hzf:
            ppb, tut = Hzf
            Wmr = self.current_level.get_sprite_at(ppb, tut, "Hkx")
            if not Wmr:
                Wmr = self.current_level.get_sprite_at(ppb, tut, "NTi")
                if Wmr: ATn = True  # clicked on NTi (empty tile)
            if Wmr:
                self.blr = Wmr  # clicked tile
                kMO = 5
    if kMO is None and Hzf is not None:
        # Clicked on empty space or bsT target
        uTB = Hzf and self.current_level.get_sprite_at(Hzf[0], Hzf[1], "bsT")
        if self.level_index == 0 and self.zth and not uTB:
            self.our = 4  # tutor penalty blink
            return
        self.complete_action(); return
    GBS = [  # neighbor offsets (3x3 grid, 4px spacing)
        [(-1,-1),(0,-1),(1,-1)],
        [(-1,0),(0,0),(1,0)],
        [(-1,1),(0,1),(1,1)],
    ]
    # Determine pattern: use level pattern or NTi-detected pattern
    if ATn:
        # NTi pattern: positions where pixel == 6 become active
        eHl = [[0,0,0],[0,1,0],[0,0,0]]
        bBi = self.blr.pixels
        for j in range(3):
            for i in range(3):
                if bBi[j][i] == 6:
                    eHl[j][i] = 1
    else:
        eHl = self.irw  # level-defined pattern
    # Apply pattern: cycle color at each active neighbor position
    if kMO == 5:
        for i in range(3):
            for j in range(3):
                if eHl[j][i] == 1:
                    ybc, lga = GBS[j][i]
                    cAw = (self.blr.x + (ybc * 4), self.blr.y + (lga * 4))
                    RfH = self.current_level.get_sprite_at(cAw[0], cAw[1], "Hkx")
                    if not RfH:
                        RfH = self.current_level.get_sprite_at(cAw[0], cAw[1], "NTi")
                    if RfH:
                        kNa = self.gqb.index(RfH.pixels[1][1])  # find current color index
                        kNa = (kNa + 1) % len(self.gqb)
                        RfH.color_remap(RfH.pixels[1][1], self.gqb[kNa])  # cycle to next
    # Check win
    if self.cgj():
        self.next_level()
        self.complete_action(); return
    if not self.lpw.lph():
        self.lose()
    self.complete_action()
~~~

### cgj() — Win Condition (line 2436)
~~~python
def cgj(self) -> bool:
    for etf in self.gig:  # each bsT target sprite
        nRq = etf.pixels[1][1]  # target center color
        # Check 8 surrounding positions (3x3 grid, 4px spacing)
        for dx, dy in [(-4,-4),(0,-4),(4,-4),(-4,0),(4,0),(-4,4),(0,4),(4,4)]:
            HJd = etf.pixels[dy//4+1][dx//4+1] == 0  # 0 = match, else = mismatch
            tx, ty = etf.x + dx, etf.y + dy
            PML = self.current_level.get_sprite_at(tx, ty, "Hkx")
            if not PML: PML = self.current_level.get_sprite_at(tx, ty, "NTi")
            if PML:
                pbA = (PML.pixels[1][1] == nRq) if HJd else (PML.pixels[1][1] != nRq)
                if not pbA: return False
    return True
~~~
- Each `bsT` sprite's 3x3 pixel glyph encodes expected/blocked at 8 neighbor positions
- Position `(dx//4+1, dy//4+1)` in target sprite pixels: 0 = expect match, non-0 = expect mismatch
- Win = all checked positions satisfy the match/mismatch constraint

### Sprite Tags
| Tag | Meaning | Visual | Size |
|-----|---------|--------|------|
| Hkx | Clickable tile — 3×3 pixel, center color cycles | 3×3 colored | 3px |
| NTi | Inactive/empty tile — has 6 (transparent) pixels for pattern | 3×3 mixed | 3px |
| bsT | Target sprite — 3×3 pixel glyph encodes 8 neighbor constraints | 3×3 colored | 3px |
| Ycb | Level 0 tutor sprite — blinking border | 2×2 colored | 2px |
- Other sprites: AcT(2×2), aIV(2×2), AzN(2×2), bdj(2×2), bqV(1×5 bar), bzH(9×9 cross)

### Level Data
- `kCv`: step counter limit
- `cwU`: color palette array (list of color indices)
- `elp`: 3×3 pattern mask (0=inactive, 1=cycle color)

### Action Sequence
1. CLICK on an Hkx or NTi tile at display coords (x, y)
2. Screen-to-grid conversion via `camera.display_to_grid()`
3. System reads the pattern `elp` (or detects it from NTi pixel structure)
4. For each active position in the 3×3 pattern centered on clicked tile:
   - Find the tile at that offset (Hkx or NTi)
   - Cycle its center color forward in palette `gqb`
5. Check all bsT targets: if all neighbor constraints satisfied → WIN
6. If step counter exhausted → LOSE

---

## 2. lp85 — Button Swapping Puzzle

### Source
- File: `environment_files/lp85/305b61c3/lp85.py` (21451 lines)
- Class: `Lp85` (line 21339)
- Available actions: `[6]` (CLICK)

### __init__ (line 21340)
~~~python
def __init__(self) -> None:
    kccdfjnrxn = levels[0].get_data("StepCounter") if levels else 0
    self.toxpunyqe = fonypcnqmf(bnlfrvxkob, zigwldrikf=len(levels), level_index=0)  # step counter disp
    self.uopmnplcnv = qfvvosdkqr(izutyjcpih)  # SWAP MAP from izutyjcpih data structure
    super().__init__(game_id="lp85", levels=levels, camera=qroguobpp, available_actions=[6])
~~~
- Camera: 16×16 viewport
- `uopmnplcnv`: dict[str, dict[str, thembpsuoz]] — swap configuration indexed by level name and button ID

### on_set_level (line 21362)
~~~python
def on_set_level(self, level: Level) -> None:
    self.izmredwten()  # update step counter
    isjnflak = self.current_level.grid_size
    if isjnflak is not None:
        self.kshrbnrfkopq = isjnflak[0]; self.papamfmeoa = isjnflak[1]
    self.ucybisahh = self.current_level.get_data("level_name")  # level identifier for swap map
    self.afhycvvjg = self.current_level.get_sprites_by_tag("sys_click")  # clickable sprites
    # Remove duplicate sys_click at same position (overlapping sprites)
    qsdpkqvbun: set[tuple[int, int]] = set()
    for s in self.afhycvvjg:
        if (s.x, s.y) in qsdpkqvbun:
            s.tags.remove("sys_click")
        else:
            qsdpkqvbun.add((s.x, s.y))
~~~

### step (line 21394)
~~~python
def step(self) -> None:
    vctdsvnwjd = False
    if self.action.id == GameAction.ACTION6:  # CLICK
        x = self.action.data.get("x", 0)
        y = self.action.data.get("y", 0)
        vshsqyfvro = self.camera.display_to_grid(x, y)
        if vshsqyfvro:
            yrtwgqlvm, ejftlnclv = vshsqyfvro
            cwpawmamb = self.pubeyzotzr(yrtwgqlvm, ejftlnclv)  # get ALL sprites at position
            if cwpawmamb is not None:
                for pnrmgmcmh in cwpawmamb:
                    if pnrmgmcmh.tags and "button" in pnrmgmcmh.tags[0]:
                        vctdsvnwjd = True
                        qrjqfnfrjr = pnrmgmcmh.tags[0].split("_")
                        if len(qrjqfnfrjr) == 3:
                            racnaqksms = qrjqfnfrjr[1]  # button ID
                            weskkxahis = qrjqfnfrjr[2]  # "R" or "L" direction
                            kypahuoyom = True if weskkxahis == "R" else False
                            dshozwexhv = chmfaflqhy(
                                self.ucybisahh,  # level name
                                racnaqksms,       # button ID
                                kypahuoyom,       # direction (R=right, L=left)
                                self.uopmnplcnv,  # swap map
                            )
                            # Move sprites to new positions
                            for pmpudfwvhx, kvtywzwzuc in dshozwexhv:
                                dbonbayerv = self.ttawusezqc(
                                    pmpudfwvhx.x * crxpafuiwp,  # 3x grid scale
                                    pmpudfwvhx.y * crxpafuiwp,
                                )
                                if dbonbayerv:
                                    dbonbayerv.set_position(
                                        kvtywzwzuc.x * crxpafuiwp,
                                        kvtywzwzuc.y * crxpafuiwp,
                                    )
    if not vctdsvnwjd:
        self.complete_action(); return
    # Win check
    if self.khartslnwa():
        self.next_level()
        self.complete_action(); return
    if not self.toxpunyqe.xsfawdkqoi():
        self.lose()
    self.complete_action()
~~~

### chmfaflqhy() — Button Translation (line 21265)
~~~python
def chmfaflqhy(
    uwtopyjnbz: str,           # level name
    ihcexiqgys: str,           # button ID
    kiofvrbmju: bool,          # R=True, L=False
    uopmnplcnv: Dict[str, Dict[str, thembpsuoz]],  # swap map
) -> List[Tuple[rnbcvtkqiw, rnbcvtkqiw]]:
    gdmraryfrp = uopmnplcnv[uwtopyjnbz][ihcexiqgys]  # button config
    qcmzcjocmj = gdmraryfrp["qcmzcjocmj"]  # dict[int, rnbcvtkqiw] position map
    oxbwsencfv = gdmraryfrp["oxbwsencfv"]  # number of positions
    if oxbwsencfv <= 1: return []
    result = []
    for acnxhwymfw, pmpudfwvhx in qcmzcjocmj.items():
        # Calculate next position index (R=+1, L=-1 with wrap)
        if kiofvrbmju:
            ibwabdeure = 1 if acnxhwymfw == oxbwsencfv else acnxhwymfw + 1
        else:
            ibwabdeure = oxbwsencfv if acnxhwymfw == 1 else acnxhwymfw - 1
        kvtywzwzuc = qcmzcjocmj[ibwabdeure]
        result.append((pmpudfwvhx, kvtywzwzuc))
    return result
~~~

### khartslnwa() — Win Condition (line 21442)
~~~python
def khartslnwa(self) -> bool:
    # bghvgbtwcb sprites need 'goal' tag at offset (1,1)
    ngnionqsbv = self.current_level.get_sprites_by_tag("bghvgbtwcb")
    for praflotbfn in ngnionqsbv:
        if self.current_level.get_sprite_at(praflotbfn.x + 1, praflotbfn.y + 1, "goal") is None:
            return False
    # fdgmtkfrxl sprites need 'goal-o' tag at offset (1,1)
    ngnionqsbv = self.current_level.get_sprites_by_tag("fdgmtkfrxl")
    for praflotbfn in ngnionqsbv:
        if self.current_level.get_sprite_at(praflotbfn.x + 1, praflotbfn.y + 1, "goal-o") is None:
            return False
    return True
~~~

### Key Constants
- `crxpafuiwp = 3`: grid scale factor (sprites positioned at multiples of 3 in game coordinates)

### Sprite Tags
| Tag | Meaning |
|-----|---------|
| `sys_click` | Any clickable sprite (deduplicated per position)
| `button_X_R/L` | Button sprite: X=button ID, R=rotate right, L=rotate left
| `bghvgbtwcb` | Sprite that needs `goal` at (x+1, y+1)
| `fdgmtkfrxl` | Sprite that needs `goal-o` at (x+1, y+1)
| `goal` | Target marker for bghvgbtwcb
| `goal-o` | Target marker for fdgmtkfrxl

### Level Data
- `StepCounter`: max steps
- `level_name`: identifier key for swap map

### Action Sequence
1. CLICK at display coordinates
2. Screen-to-grid conversion
3. Find all sprites at that position (use `pubeyzotzr` for rectangle overlap, not point)
4. If a sprite has tag starting with "button":
   - Parse tag format: `button_X_R/L`
   - Call `chmfaflqhy(level_name, button_id, direction, swap_map)`
   - Returns list of `(from_pos, to_pos)` pairs
   - For each pair: move sprite at `from_pos × 3` to `to_pos × 3`
5. Win check: every `bghvgbtwcb` must have `goal` at offset (1,1), every `fdgmtkfrxl` must have `goal-o` at (1,1)
6. Lose if steps exhausted

---

## 3. r11l — Drag-to-Connect Wiring Puzzle

### Source
- File: `environment_files/r11l/495a7899/r11l.py` (1849 lines)
- Class: `R11l` (line 1404)
- Available actions: `[6]` (CLICK)

### __init__ (line 1405)
~~~python
def __init__(self) -> None:
    self._step_counter_ui = rjtqizgnlf(ddlxmmixxo=60)
    self._max_actions = 60
    self.wiayqaumjug = None  # SELECTED sprite (clickable dot)
    self.holbcmkehyf = 0     # current index in sorted clickable list
    self.jtqexauuzid = []    # action inputs for all grid positions
    # Generate 256 action inputs (64×64 / 4×4 grid)
    for lugjhyvbpda in range(0, 64, 4):
        for fcuuuylahgr in range(0, 64, 4):
            rgktpamtctw = ActionInput(id=GameAction.ACTION6.value, data={"x": fcuuuylahgr, "y": lugjhyvbpda})
            self.jtqexauuzid.append(rgktpamtctw)
    self.kacotwgjcyq = {}   # group sprites by name pattern
    self.bbijaigbknc = []    # CLICKABLE sprites (connector dots)
    self.tdriqoljcbs = []    # WALL sprites (obstacles)
    self.yfbjozweime = False # dragging in progress
    self.qvnmfoxseus = 0     # animation frame counter
    self.havofgepjpl = 1     # animation speed (frames per unit)
    self.sgdntmcrxpq = (0,0) # start position for drag
    self.nqbqaxbtdej = (0,0) # end position for drag
    self.npvvaucvsot = False # overshoot flag
    self.yledlprvvkb = 0     # collision counter (5 → lose)
    self.flgzyjcqcspeg = False # alarm state active
    self.flgdcqnkdomzf = 0
    self.fljpbsiftilwa = 0
    self.xaalmogcsnh = {}    # alarm trackers by group
    super().__init__(game_id="r11l", levels=levels, camera=..., available_actions=[6])
~~~

### on_set_level (line 1463)
- Extracts group names from sprites with prefixes: `roefwu-`, `roefwulewcui-`, `flkdtg-`
- Builds `kacotwgjcyq` = dict mapping group ID → {roduyfsmiznvg (source), lecfirgqbwunn (connectors), gosubdcyegamj (goal)}
- `tdriqoljcbs` = sprites with `wakneh-` prefix (walls)
- `bbijaigbknc` = all connector dots from all groups
- Sorted by distance from origin (nearest first)
- First connector highlighted (color remap 3→0)
- Groups with ≥2 connectors: center the source sprite at average of connector positions
- `owuypsqbino` = sprites with `puukul-` prefix (absorbable colors)
- Wire renderer `mhucvxpgpcq` added to camera interfaces

### step (line 1805)
~~~python
def step(self) -> None:
    tffqfkxdpf = self._max_actions - self._action_count
    self._step_counter_ui.xfolsippxk(tffqfkxdpf)
    if self._action_count >= self._max_actions:
        self.lose(); self.complete_action(); return
    xqpshpiqtcq = self.action
    if self.yfbjozweime:  # dragging in progress → continue animation
        self.ltkvhywjqa()
        if not self.yfbjozweime:
            self.complete_action()
        return
    if xqpshpiqtcq.id == GameAction.ACTION6:  # CLICK
        shpscnkkub = xqpshpiqtcq.data.get("x", 0)
        hypfkfzmjk = xqpshpiqtcq.data.get("y", 0)
        xszukfqfur = self.camera.display_to_grid(shpscnkkub, hypfkfzmjk)
        if xszukfqfur:
            mbgbsxgaglu, hanvyecyntc = xszukfqfur
            nzdfcwudld = None
            # Check if click is ON a connector dot
            for i, njqtixodnb in enumerate(self.bbijaigbknc):
                if njqtixodnb.x <= mbgbsxgaglu < njqtixodnb.x + njqtixodnb.width and \
                   njqtixodnb.y <= hanvyecyntc < njqtixodnb.y + njqtixodnb.height:
                    nzdfcwudld = njqtixodnb
                    self.holbcmkehyf = i
                    break
            if nzdfcwudld:
                # SELECT this connector
                self.ecernfbexd(nzdfcwudld)
                self.complete_action()
            elif self.wiayqaumjug:
                # DRAG to this position
                sbrblfpykl = self.wiayqaumjug.width // 2
                vdrreavphg = self.wiayqaumjug.height // 2
                wkrkdqxmja = mbgbsxgaglu - sbrblfpykl
                adpghqxqvs = hanvyecyntc - vdrreavphg
                if not self.gabrtablhx(wkrkdqxmja, adpghqxqvs):
                    # Valid drag target (no wall collision)
                    self.hcpsunmfnx(wkrkdqxmja, adpghqxqvs)
                    return  # multi-step animation starts
                else:
                    self.complete_action()  # blocked by wall
            else:
                self.complete_action()  # no selection, empty click
    self.complete_action()
~~~

### ecernfbexd() — Select Sprite (line 1529)
- Un-highlight previous sprite (color 3→0)
- Highlight new sprite (color 0→3)

### gabrtablhx() — Wall Collision Test (line 1553)
- Temporarily move sprite to (x, y), test collision with any `tdriqoljcbs` (wakneh- walls)
- Return True if blocked, False if free

### hcpsunmfnx() — Initiate Drag (line 1568)
- Set `yfbjozweime = True` (drag in progress)
- Record start `sgdntmcrxpq` and end `nqbqaxbtdej` positions

### ltkvhywjqa() — Drag Animation Engine (line 1691)
Multi-phase process:
1. **Alarm animation** (`scyubqqntl`): If in alarm state, flash warning sprite
2. **Overshoot handling** (`npvvaucvsot`): Wait for alarms to finish
3. **Win phase** (`uyawyyswbya`): If all conditions met, advance to next level
4. **Main animation** (frames increment `qvnmfoxseus` up to `havofgepjpl`):
   - Interpolate sprite position from start to end
   - Track which group the dragging dot belongs to
   - Move group source sprite to center of all connectors
   - Absorb `puukul-` sprites when source overlaps them
   - Check collision with `defgjl` (alarm triggers): alarm state on collision at max frames
5. **Win check** at max frames (lines 1759-1783):
   - Every group's source collides with goal sprite (matching color content via `ldzvchvkvp`)
   - Or for groups with `whkxtx` source: any puukul- absorbed with matching colors
6. **Reverse/release** on second click: if `yfbjozweime` and not overshot, reverse direction

### Key Functions
- `sehxptcyvq(sprite)`: returns group name of a connector dot
- `zlkgwqnxrp()`: absorb `puukul-` sprites that collide with `whkxtx` sources, transferring pixel colors
- `ldzvchvkvp(src, goal)`: compare unique non-zero color sets of two sprites
- `enzibizxql(goal)`: find a `whkxtx` source colliding with a goal with matching colors
- `scyubqqntl()`: alarm animation (flash sprite every 2 frames, expire after 5 cycles)
- `ihieafichl()`: per-group alarm trigger check and animation

### Win Condition
~~~
For each group in kacotwgjcyq:
  - Source must collide with goal
  - Source's non-zero pixel set must match goal's non-zero pixel set
  (Skip groups with "dirwzt" in their ID)
  - OR for groups via bulmhgivatv (whkxtx absorb): absorbed sprites must match goal colors
~~~

### Sprite Naming
| Prefix | Meaning |
|--------|---------|
| `roefwu-` | Source sprite (movable group center)
| `roefwulewcui-` | Connector dots (clickable, dragged)
| `flkdtg-` | Goal/target sprite
| `wakneh-` | Wall/obstacle
| `puukul-` | Absorbable color sprite
| `defgjl` | Alarm trigger
| `whkxtx` | Special source (absorbs puukul- sprites)
| `dirwzt` | Groups to skip in win check

### Action Sequence
1. CLICK on a connector dot (`roefwulewcui-`) → SELECT (highlight)
2. CLICK on empty space → DRAG selected dot to that position (tween animation)
3. During drag: source moves with connectors, absorbs puukul- sprites, checks alarm triggers
4. If all sources reach goals with matching colors → WIN
5. If alarm triggers 5 times → LOSE

---

## 4. tn36 — Drop Block with Scrolling Background

### Source
- File: `environment_files/tn36/ef4dde99/tn36.py` (2647 lines)
- Class: `Tn36` (line 2595)
- Available actions: `[6]` (CLICK)

### __init__ (line 2601)
~~~python
def __init__(self) -> None:
    camera = Camera(background=BACKGROUND_COLOR, letter_box=PADDING_COLOR)
    super().__init__(game_id="tn36", levels=levels, camera=camera, available_actions=[6])
~~~

### on_set_level (line 2605)
~~~python
def on_set_level(self, level: Level) -> None:
    # Clone clean level to fresh state
    self._levels[self._current_level_index] = self._clean_levels[self._current_level_index].clone()
    self.fdksqlmpki = ytkjoffamq(self)  # FALLING BLOCK engine
    self.lmkazecqdh = ccfrgpdila(self.fdksqlmpki)  # BACKGROUND SCROLL controller
    self.nyhaiggftp = False  # win flag
    self.pgualuszrs = False  # lose flag
~~~

### Internal Engine Class `ccfrgpila` (line 2572)
~~~python
class ccfrgpdila(yhrxffrkqu):
    _background: Sprite
    lmkazecqdh: int  # frame counter for background scroll

    @property
    def abigrshaqh(self) -> bool:
        return self._background.x < self.axbjgpzkyi.x + self.axbjgpzkyi.width

    def __init__(self, krojcwlfuq: ytkjoffamq):
        self._background = krojcwlfuq.current_level.get_sprites_by_tag(ipqpjaszxy.polqmmgekl)[0]
        sprite = krojcwlfuq.current_level.get_sprites_by_tag(ipqpjaszxy.mooordpjil)[0]
        self.lmkazecqdh = 0
        super().__init__(krojcwlfuq, sprite)

    def rzwjhftbll(self) -> None:
        self.lmkazecqdh += 1
        if self.fdksqlmpki.ziyfqaqget.level_index >= 5:
            if self.lmkazecqdh % 2 == 0:
                self.axbjgpzkyi.move(-1, 0)
        else:
            self.axbjgpzkyi.move(-1, 0)
~~~

### step (line 2612)
~~~python
def step(self) -> None:
    if self.nyhaiggftp:
        self.next_level()
        self.complete_action(); return
    if self.pgualuszrs:
        self.lose()
        self.complete_action(); return
    if self.fdksqlmpki.deredwcqze:
        self.fdksqlmpki.step()  # internal falling animation
    elif self.action.id == GameAction.ACTION6:
        gugj, zrlr = self.uihpdltbxp()  # grid coordinates from click
        self.fdksqlmpki.rawolunrbj(gugj, zrlr)  # DROP BLOCK at click position
        self.fdksqlmpki.wbytzlpbyr()  # update block position
        self.lmkazecqdh.rzwjhftbll()  # scroll background leftward
    if not self.fdksqlmpki.deredwcqze:
        if self.xkvjwtvanm():
            self.nyhaiggftp = True  # WIN
            return
        elif self.slpqhjqczp():
            self.pgualuszrs = True  # LOSE (bg passed dropped block)
            return
        self.complete_action()
~~~

### Win/Lose Conditions
~~~python
def xkvjwtvanm(self) -> bool:
    return self.fdksqlmpki.vklyonlcrw  # block placed at correct position

def slpqhjqczp(self) -> bool:
    return not self.lmkazecqdh.abigrshaqh  # background scrolled past sprite

def uihpdltbxp(self) -> Tuple[int, int]:
    result = self.camera.display_to_grid(self.action.data["x"], self.action.data["y"])
    if result is None: return (0, 0)
    return result
~~~

### Internal State
- `fdksqlmpki.deredwcqze`: True while falling animation is running
- `fdksqlmpki.vklyonlcrw`: True when block is placed in correct position (win)
- `fdksqlmpki.rawolunrbj(x, y)`: initiate block drop at grid coords
- `fdksqlmpki.wbytzlpbyr()`: update block animation for one frame
- `fdksqlmpki.ziyfqaqget.level_index`: level index (≥5 changes scroll speed)
- `lmkazecqdh.abigrshaqh`: background still has room (left edge < sprite right edge)
- `lmkazecqdh.rzwjhftbll()`: move background left by 1px per call (or 2px per call even frames for levels 5+)

### Action Sequence
1. CLICK at display coordinates → grid conversion via `uihpdltbxp`
2. `fdksqlmpki.rawolunrbj(x, y)` — drop block at clicked position
3. `fdksqlmpki.wbytzlpbyr()` — update block position
4. `lmkazecqdh.rzwjhftbll()` — scroll background left
5. Loop until dropping done:
   - Win: block dropped in correct position → `nyhaiggftp = True`
   - Lose: background scrolled past block position → `pgualuszrs = True`

---

## 5. vc33 — Swap-Half & Rotate Puzzle with Light Beams

### Source
- File: `environment_files/vc33/5430563c/vc33.py` (2124 lines)
- Class: `Vc33` (line 1829)
- Available actions: `[6]` (CLICK)

### __init__ (line 1835)
~~~python
def __init__(self) -> None:
    self.heczcoeosi = xclqwacrmx(0)  # step counter display
    camera = Camera(background=BACKGROUND_COLOR, letter_box=PADDING_COLOR, interfaces=[self.heczcoeosi])
    super().__init__(game_id="vc33", levels=levels, camera=camera, available_actions=[6])
~~~

### on_set_level (line 1894)
- Reads `Gravity` tuple from level data → `self.dwwmpxqsza`
- Builds `wrcxjliglr`: pairs each `0022jvmlspyigc` (swap sprite) with two `0043nzrtobajqi` (axis sprites)
- Pairing algorithm:
  1. Find all `0043nzrtobajqi` on same row/column
  2. Find nearest of each facing (before/after along axis)
  3. Handle special cases when sprite is at edge

### step (line 2094)
~~~python
def step(self) -> None:
    if self.bnnqyrupir:  # rotation animation in progress
        if self.bnnqyrupir.xryezihexa():
            self.bnnqyrupir = None
            self.wpcgsoumbr()  # update overlays after rotation
        else:
            return  # continue animation
    elif self.action.id == GameAction.ACTION6:  # CLICK
        self.heczcoeosi.tuvumryrbp()  # decrement step counter
        wmatnlmsbs = self.action.data.get("x", 0)
        iecizdiqxl = self.action.data.get("y", 0)
        rgadpfgsms = self.camera.display_to_grid(wmatnlmsbs, iecizdiqxl)
        if rgadpfgsms:
            game_x, game_y = rgadpfgsms
            sprite = self.current_level.get_sprite_at(game_x, game_y)
            if sprite:
                if "0022jvmlspyigc" in sprite.tags:
                    # SWAP-HALF operation
                    self.iootdyzbwv(sprite)
                elif "0004sttgkofqwb" in sprite.tags:
                    # ROTATE operation (if valid position)
                    if self.ezbubuphlm(sprite):
                        self.bnnqyrupir = self.mwsdltsaxd(sprite)
                        # Hide decorative overlays
                        return  # start animation
    # Win/lose check
    if self.ielczunthe():
        self.next_level()
    elif not self.heczcoeosi.current_steps:
        self.lose()
    self.complete_action()
~~~

### Key Functions
- `iootdyzbwv(sprite)` — SWAP-HALF:
  - Gets `(yvppaekogs, dvfrzxabyk)` = the two halves from `wrcxjliglr`
  - Calls `xowbpvmzbd(yvppaekogs, dvfrzxabyk)`:
    - Move light beams with each half
    - Move halves towards each other by gravity amount
    - Crop pixels from one side, append to other
    - Rebuild overlays via `wpcgsoumbr()`

- `mwsdltsaxd(sprite)` — ROTATE animation:
  - Creates a `wqemqapjce` animation path
  - Animates sprite and its light beams through 90° rotation

- `wpcgsoumbr()` — Update overlays:
  - Remove all `0007gyluczquhi` (decorative overlays)
  - For each `0004sttgkofqwb` (rotatable piece):
    - If valid position → add `0006mfbmvylbss` or `0008rybtprnbie` overlay with matching rotation
    - Else → color the piece to error color `flmcufqvdo`

- `ielczunthe()` — WIN CHECK (line 1937):
  - For each `0016uciqlhjlom` (light beam source):
    - Get color from bottom-right pixel
    - Find first `0043nzrtobajqi` (axis sprite) along path
    - Check if any `0010gnulkywfpz` (target receptor) on same axis through walls has matching color
    - If no match found for any beam → return False
  - All beams must have a matching receptor → WIN

### Gravity/Coordinate System
- `dwwmpxqsza = (x_gravity, y_gravity)` — determines swap direction and axis
- `qhmwbtpcsk() → (x_gravity > 0 or y_gravity > 0)` — True = moves right/down, False = left/up
- `mzqwlqlkrv(sprite)` — returns y if x_gravity, else x (axis-parallel coordinate)
- `xitrlzpbgu(sprite)` — returns x if x_gravity, else y (axis-perpendicular coordinate)
- `vmjlfzxesj(sprite)` — height if x_gravity, width (axis-parallel dimension)
- `pjfzvvjgud(sprite)` — width if x_gravity, height (axis-perpendicular dimension)

### Sprite Tags
| Tag | Meaning |
|-----|---------|
| `0022jvmlspyigc` | Swap-half sprite (click to swap halves)
| `0004sttgkofqwb` | Rotatable piece (click to rotate 90°)
| `0043nzrtobajqi` | Axis/divider line
| `0007gyluczquhi` | Decorative overlay (removed/rebuilt after operations)
| `0016uciqlhjlom` | Light beam source (emits colored beam)
| `0010gnulkywfpz` | Target receptor (must match beam color)
| `0025yfyiswdvoh` | Wall (blocks light beams)
| `0001symqacyexa` | Floor (for collision detection)

### Action Sequence
1. CLICK on `0022jvmlspyigc` → SWAP-HALF:
   - Two halves move toward each other by gravity amount
   - Light beams attached to each half move with them
   - Pixels cropped from one half, appended to the other
   - Overlays rebuilt
2. CLICK on `0004sttgkofqwb` → ROTATE 90°:
   - Animation path created and executed
   - After animation: overlays rebuilt
3. WIN CHECK: every light beam must reach a receptor of matching color through walls
4. LOSE: steps exhausted

---

## 6. s5i5 — Piece Rotation & Resizing Puzzle

### Source
- File: `environment_files/s5i5/18d95033/s5i5.py` (2247 lines)
- Class: `S5i5` (line 2026)
- Available actions: `[6]` (CLICK)

### __init__ (line 2035)
~~~python
def __init__(self) -> None:
    self.gwiuiwqizb = gslihflgok(0)  # step counter
    camera = gdivpwtbrb(background=BACKGROUND_COLOR, letter_box=PADDING_COLOR, interfaces=[self.gwiuiwqizb])
    super().__init__(game_id="s5i5", levels=levels, camera=camera, available_actions=[6])
~~~

### on_set_level (line 2044)
~~~python
def on_set_level(self, level: Level) -> None:
    self.zhrkjlkeib()  # update step counter
    self.rkqyhehjqs = None
    self.fewcuujhek = -1
    self.pigtralzpb = dict()       # sizer zone → [pieces] map
    self.uricqfoplr = dict()        # piece → {children} child relationship map
    self.whoonmfbnp = dict()        # undo buffer for rollback
    onbqzewjuc = self.current_level.get_sprites_by_tag("0066ghlkyvdbgg")  # sizer zones
    for ywilvedpsj in onbqzewjuc:
        self.pigtralzpb[ywilvedpsj] = []
    ikeftojlyi = self.current_level.get_sprites_by_tag("0001qwdmnlybkb")  # pieces
    xgzeakvcwi = self.current_level.get_sprites_by_tag("0064ocqkuqacti")  # fill sprites
    for oflixwqbdt in ikeftojlyi:
        xubtnfttpv = oflixwqbdt.pixels[1, 1]  # piece center color
        # Match piece to sizer zones containing its color
        xgwwjgtqup = [ywilvedpsj for ywilvedpsj in onbqzewjuc if xubtnfttpv in ywilvedpsj.pixels]
        for ywilvedpsj in xgwwjgtqup:
            self.pigtralzpb[ywilvedpsj].append(oflixwqbdt)
        # Detect children (fill sprites colliding with this piece)
        self.uricqfoplr[oflixwqbdt] = set()
        for fmrtwxnnpy in xgzeakvcwi:
            if fmrtwxnnpy.collides_with(oflixwqbdt):
                self.uricqfoplr[oflixwqbdt].add(fmrtwxnnpy)
    # Additional children from level data "Children"
    psphsrkxjy = self.current_level.get_data("Children")
    if psphsrkxjy:
        for fdrwlflfyg in psphsrkxjy:
            orhkwrcwxo = self.current_level.get_sprites_by_name(fdrwlflfyg[0])
            zyocyrhxxh = self.current_level.get_sprites_by_name(fdrwlflfyg[1])
            for lijkrmwzvo in orhkwrcwxo:
                for atngkiijya in zyocyrhxxh:
                    self.uricqfoplr[lijkrmwzvo].add(atngkiijya)
~~~

### step (line 2181)
~~~python
def step(self) -> None:
    if self.whoonmfbnp:  # UNDO (restore to backup)
        for sprite in self.whoonmfbnp:
            zehnhpvdjw = self.whoonmfbnp[sprite]
            sprite.set_position(zehnhpvdjw.x, zehnhpvdjw.y)
            sprite.pixels = zehnhpvdjw.pixels
        self.whoonmfbnp = dict()
    elif self.action.id == GameAction.ACTION6:  # CLICK
        self.gwiuiwqizb.twwpyjzobt()  # decrement step counter
        zackclumtb = self.action.data.get("x", 0)
        pqtidnarzq = self.action.data.get("y", 0)
        hbfbhmggps = self.camera.display_to_grid(zackclumtb, pqtidnarzq)
        if hbfbhmggps:
            game_x, game_y = hbfbhmggps
            ### CASE 1: Color Button click
            aavkaktnsw = self.current_level.get_sprite_at(game_x, game_y, "0089rvqdprjwpz")
            if aavkaktnsw:
                kflqpefdye = aavkaktnsw.pixels[height//2, height//2]  # button's center color
                ikeftojlyi = self.current_level.get_sprites_by_tag("0001qwdmnlybkb")
                self.whoonmfbnp = dict()
                for oflixwqbdt in ikeftojlyi:
                    xubtnfttpv = oflixwqbdt.pixels[1, 1]  # piece center color
                    if xubtnfttpv == kflqpefdye:  # matching piece
                        self.dxlryikffn(oflixwqbdt)  # backup to undo buffer
                        orhkwrcwxo = self.find_parent(oflixwqbdt)  # parent piece
                        if orhkwrcwxo:
                            lijkrmwzvo = orhkwrcwxo[0]
                            parent_rot = self.gnpdxxlhrp(lijkrmwzvo)
                            child_rot = self.gnpdxxlhrp(oflixwqbdt)
                            # Rotate extra if parent and child are perpendicular
                            if abs(child_rot - 90 - parent_rot) == 180:
                                self.bhgumdfgqr(oflixwqbdt)  # extra rotation
                            self.bhgumdfgqr(oflixwqbdt)  # rotate 90°
                        else:
                            self.bhgumdfgqr(oflixwqbdt)  # rotate 90°
                if self.qownxibuiy():
                    return  # collision → undo on next step
                else:
                    self.whoonmfbnp = dict()  # clear undo buffer (commit)
            ### CASE 2: Sizer Zone click
            else:
                gqjxhjkgsh = self.current_level.get_sprite_at(game_x, game_y, "0066ghlkyvdbgg")
                if gqjxhjkgsh:
                    pkxvgtatly = gqjxhjkgsh.width > gqjxhjkgsh.height  # True=horizontal
                    if pkxvgtatly:
                        kjfafkvdas = gqjxhjkgsh.width // 2
                    else:
                        kjfafkvdas = gqjxhjkgsh.height // 2
                    uxmbgjysee = game_x - gqjxhjkgsh.x if pkxvgtatly else game_y - gqjxhjkgsh.y
                    self.whoonmfbnp = dict()
                    for oflixwqbdt in self.pigtralzpb[gqjxhjkgsh]:
                        self.dxlryikffn(oflixwqbdt)  # backup
                        if oflixwqbdt.height > oflixwqbdt.width:
                            index = oflixwqbdt.height // vjqemmsfmx
                        else:
                            index = oflixwqbdt.width // vjqemmsfmx
                        if uxmbgjysee > kjfafkvdas:
                            self.nkkhgerxvq(oflixwqbdt, index + 1)  # GROW
                        elif uxmbgjysee < kjfafkvdas and index > 1:
                            self.nkkhgerxvq(oflixwqbdt, index - 1)  # SHRINK
                    if self.qownxibuiy():
                        return  # collision → undo on next step
                    else:
                        self.whoonmfbnp = dict()  # commit
    # Win/lose check
    if self.neurwiqfry():
        self.next_level()
    elif not self.gwiuiwqizb.current_steps:
        self.lose()
    self.complete_action()
~~~

### Key Functions
- `bhgumdfgqr(sprite)` — ROTATE 90° around bottom-left pivot (line 2154):
  - Detects rotation from pixel pattern (`gnpdxxlhrp`)
  - Moves children via `eeyirqljyp` (recursive position + pixel rotation)
  - Adjusts sprite position based on rotation direction
  - Performs `np.rot90()` on pixels

- `nkkhgerxvq(sprite, index)` — RESIZE by index multiplier (line 2110):
  - Creates new pixel grid of size `index × vjqemmsfmx` filled with center color
  - Adjusts position based on rotation to keep anchored
  - Moves children via `uiqzouvdxd`

- `dxlryikffn(sprite)` — BACKUP to undo buffer (line 2094):
  - Clones sprite and all its children recursively

- `uiqzouvdxd(sprite, dx, dy)` — RECURSIVE MOVE (line 2088):
  - Moves sprite and all its children by (dx, dy)

- `gnpdxxlhrp(sprite)` — DETECT ROTATION (line 2100):
  - Returns 0/90/180/270 based on position of `fbnsnwoblu` (grip color) pixel

- `qownxibuiy()` — COLLISION CHECK (line 2138):
  - Returns True if any two `0001qwdmnlybkb` pieces overlap
  - Triggers UNDO on next step

- `neurwiqfry()` — WIN CHECK (line 2080):
  - All `0087vvmblxkzdi` (target zones) must be covered by `0064ocqkuqacti` (fill sprites)
  - Check: for each target zone, there exists a fill sprite at same (x, y)

### Sprite Tags
| Tag | Meaning |
|-----|---------|
| `0089rvqdprjwpz` | Color button (click to rotate all matching pieces)
| `0066ghlkyvdbgg` | Sizer zone (click to grow/shrink contained pieces)
| `0001qwdmnlybkb` | Piece (rotatable/resizable object)
| `0064ocqkuqacti` | Fill sprite (child of piece, covers target zone on win)
| `0087vvmblxkzdi` | Target zone (must be covered by fill on win)

### Constants
- `vjqemmsfmx`: base unit size for piece dimensions
- `fbnsnwoblu`: grip pixel color used for rotation detection

### Level Data
- `StepCounter`: max steps
- `Children`: list of `[parent_name, child_name]` pairs for explicit child relationships

### Undo/Collision System
- Operations execute in a trial mode:
  1. Backup sprites to `whoonmfbnp` (undo buffer)
  2. Apply transformation
  3. Check `qownxibuiy()` for overlap
  4. If collision detected → RETURN (next step restores from undo buffer)
  5. If no collision → clear undo buffer (commit)

### Action Sequence
1. **Color Button click** (tag `0089rvqdprjwpz`):
   - Extract button's center pixel color
   - Find all pieces matching that color
   - For each: rotate 90° (plus extra if parent-child perpendicular)
   - Check collisions → undo if overlap, commit if clear

2. **Sizer Zone click** (tag `0066ghlkyvdbgg`):
   - Detect click position relative to zone center
   - If beyond center → GROW (index + 1)
   - If before center → SHRINK (index - 1, min 1)
   - Check collisions → undo if overlap, commit if clear

3. WIN: All target zones covered by fill sprites
4. LOSE: Steps exhausted

---

## Cross-Game Pattern Summary for Symbolic Solver Design

### Shared Architecture
| Feature | ft09 | lp85 | r11l | tn36 | vc33 | s5i5 |
|---------|------|------|------|------|------|------|
| Camera | 16×16 | 16×16 | 64×64 | level | level | level |
| Step counter UI | sve | fonypcnqmf | rjtqizgnlf | — | xclqwacrmx | gslihflgok |
| Undo system | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Multi-step anim | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Collision check | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |

### Click Mechanics by Game
| Game | Click target | Operation | Animation? |
|------|-------------|-----------|------------|
| ft09 | Hkx (3×3 tile) | Cycle color in palette | Instant |
| lp85 | button_X_R/L | Swap positions via map | Instant |
| r11l | Connector dot → space | Select → drag tween | ✅ Multi-step |
| tn36 | Any grid position | Drop block, scroll bg | ✅ Multi-step |
| vc33 | 0022jvmlspyigc / 0004sttgkofqwb | Swap halves / rotate | ✅ On rotate |
| s5i5 | 0089rvqdprjwpz / 0066ghlkyvdbgg | Rotate pieces / resize | Instant + undo |

### Win Condition Types
| Game | Win Check | Mechanism |
|------|-----------|-----------|
| ft09 | `cgj()` — ∀ bsT: neighbor colors match pattern | Color state comparison |
| lp85 | `khartslnwa()` — pieces on goal markers | Position check at offset |
| r11l | `ltkvhywjqa()` — sources colliding with goals matching color content | Collision + color set equality |
| tn36 | `xkvjwtvanm()` — block placed correctly | Internal engine flag |
| vc33 | `ielczunthe()` — light beams reach matching receptors | Ray intersection + color match through walls |
| s5i5 | `neurwiqfry()` — all target zones covered by fill | Position equality check |

### Symbolic Solver Recommendations
1. **State representation**: Each game state = sprite positions + pixel color matrices + action counter
2. **Action encoding**: Action6 = (click_x_display, click_y_display) → grid transform
3. **Win predicate detection**: Per-game function with sprite tags as semantic anchors
4. **Effect simulation**: Per-game step() function is the ground truth model
5. **Action space**: All (x,y) within camera viewport at spacing=4 for grid-aligned clicks
6. **Pattern extraction**: From level data structures (cwU palettes, elp patterns, Gravity tuples, Children lists)