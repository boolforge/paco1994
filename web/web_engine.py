"""
web_engine.py -- Pyodide-side bridge. Reuses engine/formats.py,
engine/game_data.py, and engine/interaction.py UNCHANGED (they have no
pygame dependency) and implements a minimal numpy-array renderer instead
of engine/engine.py's pygame-based one, since a raw RGB buffer handed to
an HTML canvas is far more reliable inside Pyodide/WASM than driving SDL.
"""
import numpy as np
from pathlib import Path

from engine import formats
from engine.game_data import GameState, fire_dialogue
from engine import interaction

NATIVE_W, NATIVE_H = 320, 200
_assets_dir = None
_state = GameState()
_scene = None
_background_rgb = None
_sprite_sheet_rgb = None
_frame = np.zeros((NATIVE_H, NATIVE_W, 3), dtype=np.uint8)


def _pcx_to_rgb(path: Path) -> np.ndarray:
    data = path.read_bytes()
    pixels, w, h, palette = formats.decode_pcx(data)
    idx = np.frombuffer(pixels, dtype=np.uint8).reshape(h, w)
    pal = np.frombuffer(palette, dtype=np.uint8).reshape(256, 3)
    return pal[idx]  # fancy-index -> (h, w, 3)


def init(assets_dir: str) -> None:
    global _assets_dir
    _assets_dir = Path(assets_dir)
    load_scene("1")


def load_scene(scene_id: str, entry_pos: int = 2) -> None:
    global _scene, _background_rgb, _state
    ald = (_assets_dir / f"{scene_id}.ALD").read_bytes()
    _scene = formats.decode_ald(ald)
    alg_path = _assets_dir / f"{scene_id}.ALG"
    if alg_path.exists():
        _background_rgb = _pcx_to_rgb(alg_path)
    else:
        _background_rgb = np.zeros((NATIVE_H, NATIVE_W, 3), dtype=np.uint8)
    _state.scene_id = scene_id
    _state.dialogue_active = False
    _state.hare_x, _state.hare_y = {0: 20, 1: 300}.get(entry_pos, 160), 170


def _get_sprite_sheet() -> np.ndarray:
    global _sprite_sheet_rgb
    if _sprite_sheet_rgb is None:
        p = _assets_dir / "99"
        _sprite_sheet_rgb = _pcx_to_rgb(p) if p.exists() else None
    return _sprite_sheet_rgb


def _render() -> None:
    global _frame
    _frame = _background_rgb.copy()
    sheet = _get_sprite_sheet()
    if sheet is not None and _scene:
        for disc in _scene.disc_objects:
            try:
                x1, y1, x2, y2 = formats.sprite_sheet_rect(disc.sprite_id)
            except ValueError:
                continue
            sw, sh = x2 - x1, y2 - y1
            px, py = disc.place_x, disc.place_y
            if 0 <= py and py+sh <= NATIVE_H and 0 <= px and px+sw <= NATIVE_W:
                _frame[py:py+sh, px:px+sw] = sheet[y1:y2, x1:x2]
    # Paco placeholder marker
    hx, hy = _state.hare_x, _state.hare_y
    y0, y1_, x0, x1_ = max(0,hy-18), min(NATIVE_H,hy+4), max(0,hx-6), min(NATIVE_W,hx+6)
    _frame[y0:y1_, x0:x1_] = [220, 30, 30]
    if _state.dialogue_active:
        _frame[155:200, :] = [0, 0, 0]


def get_frame_rgb():
    _render()
    return _frame.flatten().tolist()


def get_dialogue_text() -> str:
    return _state.dialogue_text if _state.dialogue_active else ""


# -- Engine callback interface used by interaction.py handlers --------------
def transition_to_scene(dest_scene: str, dest_door: int, dest_pos: int) -> None:
    load_scene(dest_scene.replace(".ALD", "").replace(".ald", ""), dest_pos)


def show_dialogue(text: str, als_file) -> None:
    _state.dialogue_active = True
    _state.dialogue_text = text


def handle_click(x: int, y: int) -> None:
    if _state.dialogue_active:
        _state.dialogue_active = False
        return
    if _scene:
        interaction.dispatch_click(x, y, _scene, _state,
                                   __import__(__name__))
