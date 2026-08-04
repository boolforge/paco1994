"""
web_engine.py -- Pyodide-side bridge. Overwritten to leverage the real
engine/engine.py's Paco1994Engine directly, integrating standard Pygame-ce
on-canvas rendering with clean JS-bridge interfaces for audio and editor support.
"""
from pathlib import Path
import numpy as np

from engine import formats
from engine.engine import Paco1994Engine
from engine.game_data import GameState

_assets_dir = None
engine = None
_last_played_dialogue_file = None

def init(assets_dir: str) -> None:
    global _assets_dir, engine
    _assets_dir = Path(assets_dir)
    engine = Paco1994Engine(str(_assets_dir))
    engine.load_scene("1")

def tick() -> None:
    """Invoked per frame by requestAnimationFrame to render game loop."""
    if engine:
        engine.render_frame()

def handle_click(x: int, y: int) -> None:
    if engine:
        engine.handle_click(x, y)

def get_dialogue_state() -> dict:
    """Returns the dialogue state so JS can show subtitle text and trigger audio."""
    global _last_played_dialogue_file
    if not engine or not engine.state.dialogue_active:
        return {"active": False, "text": "", "audio_file": None}

    # Check if we have an audio clip to play
    audio_file = None
    # We map the active dialogue to its original ALS sound if available
    # The active dialogue text is stored in engine.state.dialogue_text
    # Let's see if we can find a matching dialogue with an ALS file
    # We can search through the DIALOGUES dict for a match or check if we loaded any ALS
    # Wait, engine.show_dialogue(text, als_file) sets self.state.dialogue_text = text.
    # We can hook show_dialogue or just check if we have a way to match it.
    # Better: let's add an 'active_als_file' to engine.state or track it!
    # Let's inspect the active dialogue
    current_text = engine.state.dialogue_text
    from engine.game_data import DIALOGUES
    for dkey, dval in DIALOGUES.items():
        if dval.text_en == current_text or dval.text_es == current_text:
            if dval.als_file:
                audio_file = dval.als_file
                break

    # If we have an audio file that hasn't been played in this dialogue session, trigger it!
    trigger_play = False
    if audio_file and audio_file != _last_played_dialogue_file:
        _last_played_dialogue_file = audio_file
        trigger_play = True
    elif not audio_file:
        _last_played_dialogue_file = None

    return {
        "active": True,
        "text": current_text,
        "audio_file": audio_file if trigger_play else None
    }

def clear_dialogue_audio_trigger() -> None:
    global _last_played_dialogue_file
    _last_played_dialogue_file = None

def get_als_pcm(filename: str) -> dict:
    """Decodes Creative VOC PCM bytes for JS Web Audio playback."""
    path = _assets_dir / filename
    if path.exists():
        try:
            pcm_bytes, rate = formats.decode_voc(path.read_bytes())
            return {
                "rate": rate,
                "pcm": list(pcm_bytes)
            }
        except Exception as e:
            print(f"Error decoding VOC {filename}: {e}")
    return None

# -- Visual Level CRUD Editor support helpers ---------------------------------

def get_scene_background_rgba(scene_id: str) -> list:
    """Decodes .ALG background to RGBA pixels for visual workspace rendering."""
    alg_path = _assets_dir / f"{scene_id}.ALG"
    if alg_path.exists():
        try:
            pixels, w, h, palette = formats.decode_pcx(alg_path.read_bytes())
            idx = np.frombuffer(pixels, dtype=np.uint8)
            pal = np.frombuffer(palette, dtype=np.uint8).reshape(256, 3)
            rgb = pal[idx]
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[..., :3] = rgb
            rgba[..., 3] = 255
            return rgba.flatten().tolist()
        except Exception as e:
            print(f"Error decoding background {scene_id}: {e}")
    return [0] * (320 * 200 * 4)

def get_sprite_rgba(sprite_id: int) -> dict:
    """Decodes individual sprite item with transparency from 99.ALG."""
    p = _assets_dir / "99"
    if p.exists():
        try:
            x1, y1, x2, y2 = formats.sprite_sheet_rect(sprite_id)
            pixels, w, h, palette = formats.decode_pcx(p.read_bytes())
            idx = np.frombuffer(pixels, dtype=np.uint8).reshape(h, w)
            pal = np.frombuffer(palette, dtype=np.uint8).reshape(256, 3)

            crop_idx = idx[y1:y2, x1:x2]
            crop_h, crop_w = crop_idx.shape
            rgb = pal[crop_idx]

            rgba = np.zeros((crop_h, crop_w, 4), dtype=np.uint8)
            rgba[..., :3] = rgb

            # Decode transparency mask (stored in mask rows at Y + 56)
            mask_idx = idx[y1+56:y2+56, x1:x2]
            alpha = np.where(mask_idx != 0, 255, 0).astype(np.uint8)
            rgba[..., 3] = alpha

            return {
                "width": crop_w,
                "height": crop_h,
                "rgba": rgba.flatten().tolist()
            }
        except Exception as e:
            print(f"Error decoding sprite {sprite_id}: {e}")
    return None

def decode_ald_data(encoded_hex: str) -> dict:
    """Decrypts XOR-0xFF encoded .ALD hex string into clean structured JSON."""
    try:
        raw_bytes = bytes.fromhex(encoded_hex)
        scene = formats.decode_ald(raw_bytes)

        objects = []
        for obj in scene.objects:
            objects.append({
                "obj_id": obj.obj_id,
                "x1": obj.x1,
                "y1": obj.y1,
                "x2": obj.x2,
                "y2": obj.y2,
                "is_door": obj.is_door,
                "dest_scene": obj.dest_scene,
                "dest_door": obj.dest_door,
                "dest_pos": obj.dest_pos
            })

        disc_objects = []
        for disc in scene.disc_objects:
            disc_objects.append({
                "sprite_id": disc.sprite_id,
                "sheet_x1": disc.sheet_x1,
                "sheet_y1": disc.sheet_y1,
                "sheet_x2": disc.sheet_x2,
                "sheet_y2": disc.sheet_y2,
                "place_x": disc.place_x,
                "place_y": disc.place_y
            })

        return {
            "scene_id": scene.scene_id,
            "music": scene.music,
            "objects": objects,
            "disc_objects": disc_objects
        }
    except Exception as e:
        return {"error": str(e)}

def encode_ald_data(scene_json: dict) -> str:
    """Serializes edited structured layout back to original XOR-0xFF ciphered hex."""
    try:
        lines = []
        lines.append(str(scene_json["scene_id"]))
        lines.append(str(scene_json["music"]))
        lines.append(str(len(scene_json["objects"])))
        lines.append(str(len(scene_json["disc_objects"])))

        for obj in scene_json["objects"]:
            lines.append(str(obj["obj_id"]))
            lines.append(str(obj["x1"]))
            lines.append(str(obj["y1"]))
            lines.append(str(obj["x2"]))
            lines.append(str(obj["y2"]))
            lines.append("1" if obj["is_door"] else "0")
            if obj["is_door"]:
                lines.append(str(obj["dest_scene"]))
                lines.append(str(obj["dest_door"]))
                lines.append(str(obj["dest_pos"]))

        lines.append("99")

        for disc in scene_json["disc_objects"]:
            lines.append(str(disc["sprite_id"]))
            # Recalculate original sheet coordinate fields based on our solved geometry formulas
            col, row = formats.sprite_index_to_cell(int(disc["sprite_id"]))
            sx1 = formats.sprite_sheet_column_x1(col)
            sy1 = 17 + row * 26
            sx2 = sx1 + formats.SPRITE_SHEET_COL_WIDTH
            # Apply original source bug: GRABAR writes Y2 as Y1 + 39 (instead of correct height + 24)
            sy2 = sy1 + formats.SPRITE_SHEET_COL_WIDTH # buggy Y2!

            lines.append(str(sx1))
            lines.append(str(sy1))
            lines.append(str(sx2))
            lines.append(str(sy2))
            lines.append(str(disc["place_x"]))
            lines.append(str(disc["place_y"]))

        text = "\r\n".join(lines) + "\r\n"
        encoded = bytes(ord(c) ^ 0xFF for c in text)
        return encoded.hex()
    except Exception as e:
        return f"ERROR: {e}"
