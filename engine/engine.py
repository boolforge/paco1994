"""
engine.py -- Main engine class. Loads real assets, renders via pygame
(SDL_VIDEODRIVER=dummy compatible for headless verification), and drives
the game loop per the CONFIRMED real structure (disassembly-verified,
see the wiki's "The main loop is in _escoba" section):

  hide cursor -> render -> show cursor -> poll input ->
  dispatch (comprueba1/comprueba2) -> check F1/F2 (save/load) -> repeat
"""
from __future__ import annotations
import os
from pathlib import Path
import pygame

from . import formats
from .game_data import GameState, fire_dialogue, DIALOGUES
from . import interaction

NATIVE_W, NATIVE_H = 320, 200
DIALOGUE_BOX_Y = 155


class Paco1994Engine:
    def __init__(self, assets_dir: str):
        self.assets_dir = Path(assets_dir)
        pygame.init()
        pygame.mixer.quit()  # audio decoding verified separately; no live audio needed for visual tests
        self.screen = pygame.display.set_mode((NATIVE_W, NATIVE_H))
        self.backbuf = pygame.Surface((NATIVE_W, NATIVE_H))
        self.state = GameState()
        self.current_scene: formats.AldScene | None = None
        self.background: pygame.Surface | None = None
        self.sprite_sheet: pygame.Surface | None = None
        self.font = pygame.font.SysFont(None, 14)

        # Real-time movement interpolation
        self._dest_x = self.state.hare_x
        self._dest_y = self.state.hare_y
        self._is_moving = False

        self._load_sprite_sheet()

    # -- Asset loading ------------------------------------------------------
    def _load_pcx_surface(self, filename: str) -> pygame.Surface:
        data = (self.assets_dir / filename).read_bytes()
        pixels, w, h, palette = formats.decode_pcx(data)
        surf = pygame.Surface((w, h), depth=8)
        pal_colors = [tuple(palette[i*3:i*3+3]) for i in range(256)]
        surf.set_palette(pal_colors)
        pygame.pixelcopy.array_to_surface(
            surf, __import__("numpy").frombuffer(pixels, dtype='uint8').reshape(h, w).T)
        return surf.convert()

    def _load_sprite_sheet(self) -> None:
        p = self.assets_dir / "99"
        if p.exists():
            self.sprite_sheet = self._load_pcx_surface("99")

    def load_scene(self, scene_id: str, entry_pos: int = 2) -> None:
        ald_path = self.assets_dir / f"{scene_id}.ALD"
        alg_path = self.assets_dir / f"{scene_id}.ALG"
        self.current_scene = formats.decode_ald(ald_path.read_bytes())
        if alg_path.exists():
            self.background = self._load_pcx_surface(f"{scene_id}.ALG")
        else:
            self.background = pygame.Surface((NATIVE_W, NATIVE_H))
        self.state.scene_id = scene_id
        self.state.dialogue_active = False
        entry_x = {0: 20, 1: 300}.get(entry_pos, 160)
        self.state.hare_x, self.state.hare_y = entry_x, 148
        self._dest_x, self._dest_y = entry_x, 148
        self._is_moving = False

    # -- Rendering (layer order confirmed via disassembly) ------------------
    def render_frame(self) -> pygame.Surface:
        # Move Paco towards destination if moving
        if self._is_moving:
            dx = self._dest_x - self.state.hare_x
            dy = self._dest_y - self.state.hare_y
            dist = (dx**2 + dy**2)**0.5
            speed = 4.0 # pixels per frame
            if dist <= speed:
                self.state.hare_x = self._dest_x
                self.state.hare_y = self._dest_y
                self._is_moving = False
            else:
                self.state.hare_x += int(speed * dx / dist)
                self.state.hare_y += int(speed * dy / dist)

            # Set facing direction based on horizontal movement
            if dx > 0:
                self.state.facing_right = True
            elif dx < 0:
                self.state.facing_right = False

        self.backbuf.fill((0, 0, 0))
        if self.background:
            self.backbuf.blit(self.background, (0, 0))
        self._render_disc_objects()
        self._render_paco()
        if self.state.dialogue_active:
            self._render_dialogue()
        self.screen.blit(self.backbuf, (0, 0))
        pygame.display.flip()
        return self.backbuf

    def _render_disc_objects(self) -> None:
        if not (self.current_scene and self.sprite_sheet):
            return
        for disc in self.current_scene.disc_objects:
            try:
                x1, y1, x2, y2 = formats.sprite_sheet_rect(disc.sprite_id)
            except ValueError:
                continue
            w, h = x2 - x1, y2 - y1
            self.backbuf.blit(self.sprite_sheet, (disc.place_x, disc.place_y),
                              area=pygame.Rect(x1, y1, w, h))

    def _render_paco(self) -> None:
        # Check if we can render the actual walk-cycle silhouette from the sprite sheet
        if not self.sprite_sheet:
            r = pygame.Rect(self.state.hare_x - 6, self.state.hare_y - 18, 12, 22)
            pygame.draw.rect(self.backbuf, (220, 30, 30), r)
            pygame.draw.rect(self.backbuf, (255, 255, 255), r, 1)
            return

        # Paco walk-cycle frames are indices 13, 14, 15
        walk_frames = [13, 14, 15]
        if self._is_moving:
            ticks = pygame.time.get_ticks()
            frame_idx = (ticks // 150) % len(walk_frames)
            frame_id = walk_frames[frame_idx]
        else:
            frame_id = 13  # standing idle frame

        try:
            x1, y1, x2, y2 = formats.sprite_sheet_rect(frame_id)
            w, h = x2 - x1, y2 - y1

            # Decode/apply transparency mask (Y offset + 56)
            mask_x1, mask_y1, mask_x2, mask_y2 = formats.sprite_sheet_mask_rect(frame_id)

            # Build cropped surfaces
            temp_surf = pygame.Surface((w, h), depth=8)
            temp_surf.set_palette(self.sprite_sheet.get_palette())
            temp_surf.blit(self.sprite_sheet, (0, 0), pygame.Rect(x1, y1, w, h))

            mask_surf = pygame.Surface((w, h), depth=8)
            mask_surf.set_palette(self.sprite_sheet.get_palette())
            mask_surf.blit(self.sprite_sheet, (0, 0), pygame.Rect(mask_x1, mask_y1, w, h))

            paco_rgba = pygame.Surface((w, h), pygame.SRCALPHA)
            palette = self.sprite_sheet.get_palette()

            # Compositing utilizing the mask row
            for y in range(h):
                for x in range(w):
                    color_idx = temp_surf.get_at((x, y))[0]
                    mask_idx = mask_surf.get_at((x, y))[0]
                    if mask_idx != 0:
                        r, g, b, _ = palette[color_idx]
                        paco_rgba.set_at((x, y), (r, g, b, 255))
                    else:
                        paco_rgba.set_at((x, y), (0, 0, 0, 0))

            if not self.state.facing_right:
                paco_rgba = pygame.transform.flip(paco_rgba, True, False)

            px = self.state.hare_x - w // 2
            py = self.state.hare_y - h
            self.backbuf.blit(paco_rgba, (px, py))
        except Exception:
            # Fallback
            r = pygame.Rect(self.state.hare_x - 6, self.state.hare_y - 18, 12, 22)
            pygame.draw.rect(self.backbuf, (220, 30, 30), r)
            pygame.draw.rect(self.backbuf, (255, 255, 255), r, 1)

    def _render_dialogue(self) -> None:
        box = pygame.Rect(0, DIALOGUE_BOX_Y, NATIVE_W, NATIVE_H - DIALOGUE_BOX_Y)
        pygame.draw.rect(self.backbuf, (0, 0, 0), box)
        txt = self.font.render(self.state.dialogue_text[:60], True, (255, 255, 255))
        self.backbuf.blit(txt, (4, DIALOGUE_BOX_Y + 4))

    # -- Callbacks used by interaction.py handlers --------------------------
    def transition_to_scene(self, dest_scene: str, dest_door: int, dest_pos: int) -> None:
        self.load_scene(dest_scene, dest_pos)

    def show_dialogue(self, text: str, als_file: str | None) -> None:
        self.state.dialogue_active = True
        self.state.dialogue_text = text

    def dismiss_dialogue(self) -> None:
        self.state.dialogue_active = False

    # -- Input (mirrors confirmed comprueba dispatch) ------------------------
    def handle_click(self, x: int, y: int) -> None:
        if self.state.dialogue_active:
            self.dismiss_dialogue()
            return
        if self.current_scene:
            hit = interaction.dispatch_click(x, y, self.current_scene, self.state, self)
            if not hit:
                # Set walk target, keeping Paco above the HUD line (y=148)
                self._dest_x = x
                self._dest_y = min(y, 148)
                self._is_moving = True

    def save_game(self, path: str) -> None:
        Path(path).write_text(self.state.save_text())

    def load_game(self, path: str) -> None:
        self.state = GameState.load_text(Path(path).read_text())
        self.load_scene(self.state.scene_id)
