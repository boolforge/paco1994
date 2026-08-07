"""
formats.py -- Verified file-format decoders for Paco El Hare vs Los Marcianos
Siderales (1994, Alcachofa Soft).

Every decoder here was validated against the real game assets during the
reverse-engineering pass documented in the companion wiki article
(Paco1994_ScummVM_Wiki_Article.wiki). Where a format detail is a confirmed
quirk of the original (e.g. the .ALD height-field bug), it is preserved
and commented, not "fixed" -- fidelity to the original is the goal.
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# .ALG -- PCX v3.0 backgrounds and sprite sheets
# ---------------------------------------------------------------------------

def decode_pcx(data: bytes) -> tuple[bytes, int, int, bytes]:
    """Decode a ZSoft PCX v3.0 image.

    Returns (pixel_indices, width, height, palette). pixel_indices is a
    flat bytes object of width*height palette indices (0-255).
    palette is 768 bytes (256 * RGB).
    """
    xmin, ymin, xmax, ymax = struct.unpack_from('<4H', data, 4)
    bytes_per_line = struct.unpack_from('<H', data, 66)[0]
    width = xmax - xmin + 1
    height = ymax - ymin + 1

    assert data[-769] == 0x0C, "missing VGA palette marker"
    palette = data[-768:]

    needed = height * bytes_per_line
    raw = bytearray()
    pos = 128
    while len(raw) < needed:
        b = data[pos]; pos += 1
        if (b & 0xC0) == 0xC0:
            count = b & 0x3F
            value = data[pos]; pos += 1
            raw.extend([value] * count)
        else:
            raw.append(b)

    if bytes_per_line == width:
        pixels = bytes(raw[:needed])
    else:
        # Strip row padding
        out = bytearray()
        for y in range(height):
            out.extend(raw[y*bytes_per_line : y*bytes_per_line + width])
        pixels = bytes(out)

    return pixels, width, height, palette


# ---------------------------------------------------------------------------
# .ALS -- Creative Voice File (VOC) v1.10, 8-bit unsigned PCM mono
# ---------------------------------------------------------------------------

def decode_voc(data: bytes) -> tuple[bytes, int]:
    """Decode a Creative VOC file. Returns (pcm_u8_bytes, sample_rate_hz)."""
    assert data[:19] == b'Creative Voice File'
    header_size = struct.unpack_from('<H', data, 20)[0]
    pos = header_size
    pcm = bytearray()
    rate = 0
    while pos < len(data):
        block_type = data[pos]; pos += 1
        if block_type == 0x00:
            break
        block_len = data[pos] | (data[pos+1] << 8) | (data[pos+2] << 16)
        pos += 3
        if block_type == 0x01:
            divisor = data[pos]
            rate = 1_000_000 // (256 - divisor)
            pcm.extend(data[pos+2 : pos+block_len])
        pos += block_len
    return bytes(pcm), rate


# ---------------------------------------------------------------------------
# .ALD -- scene layout data (XOR-0xFF encrypted plain text)
# ---------------------------------------------------------------------------

@dataclass
class AldObject:
    obj_id: int
    x1: int; y1: int; x2: int; y2: int
    is_door: bool
    dest_scene: str = ""
    dest_door: int = 0
    dest_pos: int = 2  # 0=left, 1=right, 2=center

    def contains(self, x: int, y: int) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


@dataclass
class AldDiscObject:
    sprite_id: int
    sheet_x1: int; sheet_y1: int
    sheet_x2: int; sheet_y2: int  # NOTE: buggy, see 99.ALG sheet geometry below
    place_x: int; place_y: int


@dataclass
class AldScene:
    scene_id: str = ""
    music: str = ""
    objects: list[AldObject] = field(default_factory=list)
    disc_objects: list[AldDiscObject] = field(default_factory=list)


def decode_ald(raw: bytes) -> AldScene:
    """Decode a .ALD scene file. `raw` is the on-disk (XOR-0xFF) bytes."""
    decoded = bytes(b ^ 0xFF for b in raw)  # _codifica(): self-inverse XOR
    text = decoded.decode('latin-1')
    lines = [l.strip() for l in text.replace('\r\n', '\n').split('\n') if l.strip()]

    p = 0
    scene = AldScene()
    scene.scene_id = lines[p]; p += 1
    scene.music = lines[p]; p += 1
    nop = int(lines[p]); p += 1
    nod = int(lines[p]); p += 1

    for _ in range(nop):
        obj_id = int(lines[p]); p += 1
        x1 = int(lines[p]); p += 1
        y1 = int(lines[p]); p += 1
        x2 = int(lines[p]); p += 1
        y2 = int(lines[p]); p += 1
        is_door = int(lines[p]) != 0; p += 1
        obj = AldObject(obj_id, x1, y1, x2, y2, is_door)
        if is_door:
            obj.dest_scene = lines[p]; p += 1
            obj.dest_door = int(lines[p]); p += 1
            obj.dest_pos = int(lines[p]); p += 1
        scene.objects.append(obj)

    assert lines[p] == "99", f"terminator mismatch: {lines[p]!r}"
    p += 1

    for _ in range(nod):
        sid = int(lines[p]); p += 1
        sx1 = int(lines[p]); p += 1
        sy1 = int(lines[p]); p += 1
        sx2 = int(lines[p]); p += 1
        sy2 = int(lines[p]); p += 1
        px = int(lines[p]); p += 1
        py = int(lines[p]); p += 1
        scene.disc_objects.append(AldDiscObject(sid, sx1, sy1, sx2, sy2, px, py))

    return scene


# ---------------------------------------------------------------------------
# 99.ALG sprite sheet geometry -- solved formula (see wiki for full derivation)
# ---------------------------------------------------------------------------

SPRITE_SHEET_COL_WIDTH = 39
SPRITE_SHEET_ROW_HEIGHT = 24
SPRITE_SHEET_MASK_Y_OFFSET = 56

def sprite_sheet_column_x1(elec: int) -> int:
    """ELEC is the 1-based column index (1-7). Formula confirmed exactly
    against SCOVA.ALC's GET statements and 11 real disc-object coordinates."""
    return 2 * elec + (elec - 1) * 39

def sprite_index_to_cell(sprite_id: int) -> tuple[int, int]:
    """Map a NUOD sprite index (2-15) to (column 1-7, row 0 or 1).
    Row 0 (sprite y=17): index = column + 1
    Row 1 (sprite y=43): index = column + 8
    Index 1 is never used by any real disc-object in any scene."""
    if 2 <= sprite_id <= 8:
        return sprite_id - 1, 0
    elif 9 <= sprite_id <= 15:
        return sprite_id - 8, 1
    raise ValueError(f"sprite_id {sprite_id} outside confirmed range 2-15")

def sprite_sheet_rect(sprite_id: int) -> tuple[int, int, int, int]:
    """Returns (x1, y1, x2, y2) of the sprite's TRUE cell in 99.ALG --
    using the confirmed real height (24px), not the buggy +39 stored
    in .ALD files."""
    col, row = sprite_index_to_cell(sprite_id)
    x1 = sprite_sheet_column_x1(col)
    y1 = 17 + row * 26  # row 0 at y=17, row 1 at y=43 (26px stride)
    return x1, y1, x1 + SPRITE_SHEET_COL_WIDTH, y1 + SPRITE_SHEET_ROW_HEIGHT

def sprite_sheet_mask_rect(sprite_id: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = sprite_sheet_rect(sprite_id)
    return x1, y1 + SPRITE_SHEET_MASK_Y_OFFSET, x2, y2 + SPRITE_SHEET_MASK_Y_OFFSET


# Paco walk-cycle sprite: found in the SAME "99" sheet, bottom third
# (y=123-200), never examined until now -- see wiki TODO. 2 rows (facing
# right/left) x 8 walk frames, each with a color cell + corresponding
# mask cell. Geometry below is approximate (clean 40px/8-col, ~19px row
# split) pending pixel-exact confirmation -- flagged, not asserted final.
PACO_SHEET_Y0 = 123
PACO_CELL_W = 40
PACO_CELL_H = 19

def paco_sprite_rect(frame: int, facing_right: bool):
    row = 0 if facing_right else 1
    x1 = frame * PACO_CELL_W
    y1 = PACO_SHEET_Y0 + row * PACO_CELL_H
    return x1, y1, x1 + PACO_CELL_W, y1 + PACO_CELL_H

def paco_mask_rect(frame: int, facing_right: bool):
    x1, y1, x2, y2 = paco_sprite_rect(frame, facing_right)
    return x1, y1 + 2*PACO_CELL_H, x2, y2 + 2*PACO_CELL_H
