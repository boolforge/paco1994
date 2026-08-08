# TODO — Paco1994 (honest, detailed, updated)

## Sprite still not visible — root cause NOT yet confirmed
Wired `formats.paco_sprite_rect()`/`paco_mask_rect()` into `engine.py`
(`_render_paco`) via commits `4e8f1bb3`/`56759f19`. User reports still
not visible. **Not yet debugged live** — candidates, untested:
1. Geometry (y=123, 40px cols, 19px rows) was a rough visual estimate,
   never pixel-verified. Likely wrong bounds -> garbage/blank crop.
2. `_render_paco` has an internal try/except; any error (e.g. bad rect,
   `GameState.facing_right` mismatch) silently falls back to the red
   placeholder with NO visible error. Needs explicit logging or a
   local repro to see the real exception, not guessing.
3. GitHub Pages CDN cache lag after push — not ruled out, not confirmed.
4. Web build vs `verify.py` may diverge (two callers of the same
   `engine.py`, but only one has been runtime-tested since the change).

**Next action when resumed**: clone fresh, run `verify.py` (cheap,
local, no browser), inspect the actual screenshot output for the Paco
region before touching the web build again. Do not patch further via
blind API edits without a render test.

## Also open (carried over, still true)
- [ ] Audio: `get_als_pcm`/`playVoicePCM` verified correct in isolation
      (Python-side decode confirmed, JS function reviewed) but never
      confirmed actually audible end-to-end in a real/headless browser.
- [ ] Inventory/menu grid (2x7, visible in UI) never wired to
      `GameState.inventory` — renders empty always.
- [ ] Dialogue/subtitle text: `get_dialogue_state()` confirmed correct
      in Python; JS-side display never confirmed visually in-browser.
- [ ] Two rendering paths risk of drift: `engine/engine.py` (pygame-ce,
      now canonical) vs an earlier abandoned numpy+Canvas
      `web_engine.py` variant — confirm only one is live.
- [ ] `_rompo`/`_rompo2`, 7x16 table at 0xC630: unresolved.
- [ ] `verify.py` puzzle-chain click coordinates: approximate, not
      pixel-verified against real `.ALD` rects.
- [ ] C++ ScummVM skeleton (`boolforge/scummvm`): does not compile.
- [ ] Paco sprite geometry itself (this session's find): needs
      pixel-exact boundary confirmation, not just visual estimate.

## Process note
Recent fixes were pushed via GitHub Contents API (no local clone) to
save tokens after repeated environment resets. This means **nothing
pushed in this batch has been runtime-verified** — API commits only
confirm the file changed, not that it works. Flagging this explicitly
rather than implying otherwise.
