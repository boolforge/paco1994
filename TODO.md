# TODO / Known Gaps — Paco1994

Tracked honestly as found, with root causes, not just symptoms. See the
wiki article's Gap Analysis and Cross-verification log for the deeper
technical background behind several of these.

## Fixed (see git log for commit-by-commit detail)

- [x] GitHub Pages served README.md instead of the game (no root
      `index.html`, no `.nojekyll`) — fixed.
- [x] `web/__pycache__` was committed to the repo — removed, `.gitignore` added.
- [x] `_load_pcx_surface()` called `.convert()`, which strips a pygame
      Surface's indexed palette. `_render_paco()` later called
      `self.sprite_sheet.get_palette()` and crashed with
      `pygame.error: Surface has no palette to get`, silently caught by
      its own `except` and falling back to a plain red square — this is
      what the plain square in-game actually was. Confirmed by direct
      reproduction outside the try/except, not assumed. Fixed by not
      converting surfaces that need palette access later.
- [x] Paco's placeholder was, for a time, drawing 99.ALG sprite-sheet
      index 13 and calling it "Paco's walk cycle." Per the wiki's
      confirmed sprite-index formula (cross-validated against 11 real
      disc-object coordinates), indices 2–15 are real puzzle/inventory
      items — index 13 specifically is a real item, not Paco. Reverted
      to an honestly-labeled placeholder rather than silently showing
      the wrong sprite. **Paco's own sprite data has never been located
      in any known copy of the original distribution.**

## Open

- [ ] **No audio anywhere in the web build.** `engine/formats.py`'s
      `decode_voc()` is correct and tested (see the wiki), but nothing
      in `web/web_engine.py` or `index.html` calls it or plays the
      result through Web Audio. `get_pcm_for_als()` was added to
      `web_engine.py` as a first step (decodes on demand) but is not
      yet wired to any JS-side `AudioContext` playback.
- [ ] **Inventory/menu grid renders empty.** The UI shows the 2×7 grid
      (matching the confirmed 99.ALG sheet layout) but nothing populates
      it from `GameState.inventory`. Needs a JS-side redraw of that grid
      driven by `state.inventory` after every relevant action.
- [ ] **Dialogue/subtitle text**: `get_dialogue_text()` exists and is
      correct in the pygame-based `engine/engine.py` path; needs
      re-verification against whichever rendering path (pygame-ce vs.
      numpy+Canvas) the project settles on — see the note below.
- [ ] **Two parallel rendering paths exist and can drift**:
      `engine/engine.py` (pygame/pygame-ce, used by `verify.py` and by
      the current web build) and the original `web/web_engine.py`
      numpy+Canvas bridge from an earlier commit. Pick one and delete
      the other rather than maintaining both — recommend keeping the
      pygame-ce path now that its actual bug (not a fundamental
      WASM/SDL problem, just the `.convert()` palette bug above) is
      fixed and confirmed working, since it already has more complete
      game logic (movement stepping, walk-cycle timing scaffold) built
      on it.
- [ ] `_rompo`/`_rompo2` and the 7×16 byte table at HARE.EXE 0xC630:
      exact semantics still unresolved (see wiki).
- [ ] Click coordinates for the simulated puzzle chain in `verify.py`
      (P01/P02/P05 etc.) are approximate, not pixel-verified against
      the real `.ALD` hotspot rects.
- [ ] C++ ScummVM engine skeleton (`boolforge/scummvm`, `engines/paco1994/`)
      does not compile — it's a documented skeleton, not an integrated
      build target.
