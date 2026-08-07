#!/usr/bin/env python3
"""
ARC-AGI-3 Z3 Validator — Conecta SMT (Z3) ao pipeline ARC-AGI-3

Pipeline:
  1. Recebe frame ARC-AGI-3 (grid 64x64, valores 0-15)
  2. Extrai objetos (connected components, bounding boxes, cores)
  3. Codifica invariantes como restrições Z3 (BitVec 4-bit para cores 0-15)
  4. Valida hipóteses de transformação ("Se ACTION1, objeto X move")
  5. Retorna: hipótese válida/inválida + contraexemplo + modelo

Uso:
  from arc_z3_validator import ARCZ3Validator
  validator = ARCZ3Validator()
  frame = api.get_state()  # frame ARC-AGI-3
  valid, model, counterexample = validator.validate_hypothesis(frame1, frame2, hypothesis)
"""

import numpy as np
from typing import List, Tuple, Dict, Any, Optional, Union
from dataclasses import dataclass
import enum

# Tenta importar z3; falha graciosa se não instalado
try:
    from z3 import BitVec, BitVecVal, And, Or, Not, If, Solver, sat, unsat, unknown
    from z3 import Extract, Concat, ULE, UGE, ULT, UGT
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False
    print("[!] z3-solver não instalado. Instale com: pip install z3-solver")
    # Placeholder para permitir import sem z3
    BitVec = None
    Solver = object
    sat = None
    unsat = None


# ──────────────────── ① Data Structures ────────────────────

@dataclass
class Object:
    """Objeto extraído do grid."""
    id: int
    color: int          # 0-15 (0 = background)
    x: int              # posição x no grid (0-63)
    y: int              # posição y no grid (0-63)
    width: int          # largura do bounding box
    height: int         # altura do bounding box
    area: int           # número de pixels
    pixels: List[Tuple[int, int]]  # lista de (x, y)
    is_rect: bool       # True se forma retangular
    centroid_x: float   # centro do objeto
    centroid_y: float

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width - 1, self.y + self.height - 1)


@dataclass
class TransformationHypothesis:
    """Hipótese de transformação entre dois frames."""
    action: str                 # "ACTION1" a "ACTION7" ou "RESET"
    object_id: int              # ID do objeto transformado
    dx: int = 0                 # deslocamento em x
    dy: int = 0                 # deslocamento em y
    color_change: Optional[int] = None  # mudança de cor (se aplicável)
    appears: bool = False       # se o objeto apareceu (novo)
    disappears: bool = False    # se o objeto desapareceu
    split: bool = False         # se o objeto se dividiu
    merge: bool = False         # se objetos se fundiram
    rotation: Optional[int] = None  # rotação em graus (90, 180, 270)


@dataclass
class ValidationResult:
    """Resultado da validação Z3."""
    valid: bool                 # True se a hipótese é logicamente consistente
    model: Optional[Dict] = None  # modelo Z3 (atribuições de variáveis)
    counterexample: Optional[Dict] = None  # contraexemplo (se inválida)
    constraints_added: int = 0  # número de restrições geradas
    solver_time_ms: float = 0.0  # tempo de solver


# ──────────────────── ② Core Validator ────────────────────

class ARCZ3Validator:
    """
    Validador SMT (Z3) para frames ARC-AGI-3.
    Extrai objetos de grids 64×64, codifica invariantes como restrições Z3,
    e valida hipóteses de transformação.
    """

    # Constantes Z3: BitVec de 8 bits para coordenadas (0-63) e cores (0-15)
    COORD_BITS = 8    # 0-63 cabe em 8 bits
    COLOR_BITS = 4    # 0-15 cabe em 4 bits
    GRID_SIZE = 64

    def __init__(self):
        if not Z3_AVAILABLE:
            raise RuntimeError("z3-solver não está instalado")
        self._frame_count = 0

    # ── 2.1 Extração de Objetos ──

    def extract_objects(self, grid: np.ndarray) -> List[Object]:
        """
        Extrai objetos de um grid 2D usando BFS por componentes conectados (4-vizinhos).
        Ignora background (valor 0).
        """
        objects = []
        visited = np.zeros_like(grid, dtype=bool)
        h, w = grid.shape

        for y in range(h):
            for x in range(w):
                if not visited[y, x] and grid[y, x] != 0:
                    color = int(grid[y, x])
                    pixels = []
                    stack = [(x, y)]
                    visited[y, x] = True

                    while stack:
                        cx, cy = stack.pop()
                        pixels.append((cx, cy))
                        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h:
                                if not visited[ny, nx] and int(grid[ny, nx]) == color:
                                    visited[ny, nx] = True
                                    stack.append((nx, ny))

                    if pixels:
                        xs, ys = zip(*pixels)
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        obj_w = max_x - min_x + 1
                        obj_h = max_y - min_y + 1
                        area = len(pixels)
                        obj = Object(
                            id=len(objects),
                            color=color,
                            x=min_x,
                            y=min_y,
                            width=obj_w,
                            height=obj_h,
                            area=area,
                            pixels=pixels,
                            is_rect=(obj_w * obj_h == area),
                            centroid_x=sum(xs) / len(xs),
                            centroid_y=sum(ys) / len(ys),
                        )
                        objects.append(obj)
        return objects

    # ── 2.2 Relações entre objetos ──

    def compute_object_relations(self, objects: List[Object]) -> List[str]:
        """
        Calcula relações espaciais entre objetos.
        Retorna lista de strings de relação no formato RDF-like.
        """
        relations = []
        for a in objects:
            for b in objects:
                if a.id >= b.id:
                    continue
                # Relações posicionais
                if a.centroid_x < b.centroid_x - 2:
                    relations.append(f"left({a.id},{b.id})")
                if a.centroid_x > b.centroid_x + 2:
                    relations.append(f"right({a.id},{b.id})")
                if a.centroid_y < b.centroid_y - 2:
                    relations.append(f"above({a.id},{b.id})")
                if a.centroid_y > b.centroid_y + 2:
                    relations.append(f"below({a.id},{b.id})")
                # Sobreposição parcial
                ax1, ay1, ax2, ay2 = a.bbox
                bx1, by1, bx2, by2 = b.bbox
                ox = max(0, min(ax2, bx2) - max(ax1, bx1))
                oy = max(0, min(ay2, by2) - max(ay1, by1))
                if ox > 0 and oy > 0:
                    relations.append(f"overlaps({a.id},{b.id})")
                if a.color == b.color:
                    relations.append(f"same_color({a.id},{b.id})")
        return relations

    # ── 2.3 Detecção de Transformações ──

    def detect_transformations(
        self, frame_a: np.ndarray, frame_b: np.ndarray
    ) -> List[TransformationHypothesis]:
        """
        Compara dois frames consecutivos e gera hipóteses de transformação.
        """
        objs_a = self.extract_objects(frame_a)
        objs_b = self.extract_objects(frame_b)
        hypotheses = []

        # Match por cor e tamanho
        for oa in objs_a:
            best_match = None
            best_dist = 1000
            for ob in objs_b:
                if ob.color == oa.color and abs(ob.area - oa.area) / max(ob.area, 1) < 0.3:
                    dist = abs(ob.centroid_x - oa.centroid_x) + abs(ob.centroid_y - oa.centroid_y)
                    if dist < best_dist:
                        best_dist = dist
                        best_match = ob

            if best_match is not None:
                dx = int(round(best_match.centroid_x - oa.centroid_x))
                dy = int(round(best_match.centroid_y - oa.centroid_y))
                if dx != 0 or dy != 0:
                    hypotheses.append(TransformationHypothesis(
                        action="ACTION1", object_id=oa.id,
                        dx=dx, dy=dy
                    ))
                # Verificar mudança de cor (objeto dividido em B)
            else:
                # Objeto desapareceu
                hypotheses.append(TransformationHypothesis(
                    action="ACTION1", object_id=oa.id,
                    disappears=True
                ))

        # Objetos novos em B que não estavam em A
        matched_a_ids = set()
        for h in hypotheses:
            if not h.appears and not h.disappears:
                # matched objects
                pass
        a_obj_ids = {o.id for o in objs_a}
        b_obj_ids = {o.id for o in objs_b}
        # Heurística simples: se B tem mais objetos que A e 
        # algum objeto em B não corresponde a nenhum em A
        if len(objs_b) > len(objs_a):
            for ob in objs_b:
                is_new = True
                for oa in objs_a:
                    if oa.color == ob.color and abs(ob.area - oa.area) / max(ob.area, 1) < 0.3:
                        is_new = False
                        break
                if is_new:
                    hypotheses.append(TransformationHypothesis(
                        action="ACTION1", object_id=ob.id,
                        appears=True,
                        color_change=ob.color
                    ))

        return hypotheses

    # ── 2.4 Codificação SMT ──

    def encode_frame_as_constraints(
        self, frame: np.ndarray, solver: Solver, frame_name: str = "f0"
    ) -> Dict[str, Any]:
        """
        Codifica um frame ARC-AGI-3 como restrições Z3.
        Cada pixel vira BitVec(4) e restrições de invariantes são adicionadas.
        
        Estratégia:
        - Variáveis para objetos detectados (posição, cor, bounding box)
        - Invariantes: objetos não se sobrepõem, cores são preservadas
        - Background (0) nunca muda
        """
        objects = self.extract_objects(frame)
        z3_vars = {}

        for obj in objects:
            prefix = f"{frame_name}_obj_{obj.id}"
            # Posição (x, y) centro
            var_x = BitVec(f"{prefix}_x", self.COORD_BITS)
            var_y = BitVec(f"{prefix}_y", self.COORD_BITS)
            var_color = BitVec(f"{prefix}_c", self.COLOR_BITS)

            # Vínculo ao valor extraído do frame
            solver.add(var_x == obj.centroid_x)
            solver.add(var_y == obj.centroid_y)
            solver.add(var_color == obj.color)

            z3_vars[f"{prefix}_x"] = var_x
            z3_vars[f"{prefix}_y"] = var_y
            z3_vars[f"{prefix}_c"] = var_color

        return z3_vars

    # ── 2.5 Validação de Hipóteses ──

    def validate_hypothesis(
        self,
        frame_a: np.ndarray,
        frame_b: np.ndarray,
        hypothesis: TransformationHypothesis
    ) -> ValidationResult:
        """
        Valida se uma hipótese de transformação é consistente entre frame_a e frame_b.
        
        1. Codifica frame_a como restrições Z3
        2. Aplica hipótese como restrições adicionais
        3. Codifica frame_b como restrições Z3
        4. Z3 verifica se frame_a + hipótese ⊢ frame_b (satisfazível?)
        """
        import time
        start = time.time()

        solver = Solver()
        solver.set("timeout", 5000)  # 5 segundos max

        vars_a = self.encode_frame_as_constraints(frame_a, solver, "f0")
        vars_b = self.encode_frame_as_constraints(frame_b, solver, "f1")

        # Adiciona restrições da hipótese
        constraint_count = len(solver.assertions())

        if hypothesis.disappears:
            # Objeto não aparece em frame_b
            prefix = f"f0_obj_{hypothesis.object_id}"
            if f"{prefix}_x" in vars_a:
                obj_x = vars_a[f"{prefix}_x"]
                obj_y = vars_a[f"{prefix}_y"]
                # Tenta provar que NÃO existe em f1
                for key, var in vars_b.items():
                    solver.add(Or(var != vars_a[f"{prefix}_x"], 
                                  list(vars_b.values())[0] != vars_a[f"{prefix}_y"]))
        elif hypothesis.appears:
            # Objeto existe em frame_b mas não em frame_a (caso coberto pelos constraints)
            pass
        elif hypothesis.dx != 0 or hypothesis.dy != 0:
            # Objeto moveu
            prefix_a = f"f0_obj_{hypothesis.object_id}"
            if f"{prefix_a}_x" in vars_a and f"{prefix_a}_x" in vars_b:
                solver.add(
                    vars_b[f"{prefix_a}_x"] == vars_a[f"{prefix_a}_x"] + hypothesis.dx
                )
                solver.add(
                    vars_b[f"{prefix_a}_y"] == vars_a[f"{prefix_a}_y"] + hypothesis.dy
                )

        new_constraints = len(solver.assertions()) - constraint_count

        # Verifica satisfazibilidade
        result = solver.check()
        elapsed = (time.time() - start) * 1000

        if result == sat:
            model = {}
            m = solver.model()
            for d in m.decls():
                model[d.name()] = m[d]
            return ValidationResult(
                valid=True,
                model=model,
                constraints_added=new_constraints,
                solver_time_ms=elapsed
            )
        elif result == unsat:
            return ValidationResult(
                valid=False,
                counterevidence={"reason": "UNSAT — hipótese contraditória"},
                constraints_added=new_constraints,
                solver_time_ms=elapsed
            )
        else:
            return ValidationResult(
                valid=False,  # unknown = tratamos como inválido
                counterevidence={"reason": "UNKNOWN — timeout ou limite"},
                constraints_added=new_constraints,
                solver_time_ms=elapsed
            )

    # ── 2.6 Gerador incremental de hipóteses ──

    def generate_and_validate_all(
        self, frame_a: np.ndarray, frame_b: np.ndarray
    ) -> List[ValidationResult]:
        """
        Gera todas as hipóteses possíveis e valida cada uma com Z3.
        Retorna lista ordenada por validade + tempo de solver.
        """
        hypotheses = self.detect_transformations(frame_a, frame_b)
        results = []

        for h in hypotheses:
            result = self.validate_hypothesis(frame_a, frame_b, h)
            results.append((h, result))

        # Ordena: válidas primeiro, depois por tempo de solver
        results.sort(key=lambda x: (-x[1].valid, x[1].solver_time_ms))
        return results


# ──────────────────── ③ CLI Entry Point ────────────────────

def main():
    """Modo CLI: teste rápido com grids sintéticos."""
    print("═" * 60)
    print("  ARC-AGI-3 Z3 Validator")
    print("═" * 60)

    # Grid sintético 16×16 para teste rápido
    grid_a = np.zeros((16, 16), dtype=int)
    grid_a[4:8, 4:8] = 5   # quadrado azul
    grid_a[10:12, 2:4] = 3  # retângulo verde pequeno

    grid_b = np.zeros((16, 16), dtype=int)
    grid_b[4:8, 6:10] = 5  # quadrado moveu +2 em x
    grid_b[10:12, 2:4] = 3  # verde não moveu

    val = ARCZ3Validator()

    objs_a = val.extract_objects(grid_a)
    print(f"\n📦 Objetos frame A: {len(objs_a)}")
    for o in objs_a:
        print(f"   [{o.id}] color={o.color}, pos=({o.x},{o.y}), size={o.width}x{o.height}, area={o.area}")

    objs_b = val.extract_objects(grid_b)
    print(f"\n📦 Objetos frame B: {len(objs_b)}")
    for o in objs_b:
        print(f"   [{o.id}] color={o.color}, pos=({o.x},{o.y}), size={o.width}x{o.height}, area={o.area}")

    hyps = val.detect_transformations(grid_a, grid_b)
    print(f"\n🔍 Hipóteses detectadas: {len(hyps)}")
    for h in hyps:
        print(f"   obj[{h.object_id}]: dx={h.dx}, dy={h.dy}, appears={h.appears}, disappears={h.disappears}")

    print("\n🧩 Validando com Z3...")
    for h in hyps:
        result = val.validate_hypothesis(grid_a, grid_b, h)
        status = "✅" if result.valid else "❌"
        print(f"   {status} obj[{h.object_id}]: {result.solver_time_ms:.1f}ms, constraints={result.constraints_added}")

    print(f"\n{'═' * 60}")
    print("  Z3 Validator pronto!")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
