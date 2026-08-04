# Paco1994

Reverse-engineered, **verified, runnable** Python reference engine for
*Paco El Hare vs Los Marcianos Siderales* (1994, Alcachofa Soft S.L.) —
a Spanish MS-DOS freeware point-and-click adventure demo, historically
significant as the direct precursor to *Drascula: The Vampire Strikes
Back*.

## What this is

- `Paco1994_ScummVM_Wiki_Article.wiki` — the complete technical writeup
  (file formats, memory map, disassembly-confirmed main loop, dialogue
  database, puzzle state machine, cross-verification log for every
  secondary source checked along the way). Written for eventual
  inclusion on wiki.scummvm.org.
- `engine/` — a working Python package implementing every confirmed
  format decoder and game-logic rule from the wiki, above.
- `verify.py` — runs the real engine headlessly against the real game
  assets, renders all 11 scenes, and walks the full confirmed puzzle
  chain (P01-P08), saving a screenshot at every step to
  `verify_output/`. This is the engine's own proof that it matches the
  reverse-engineered specification, not just a claim.
- `web/` — a browser-playable build via Pyodide (Python compiled to
  WebAssembly), served from GitHub Pages.
- `assets/original/` — the real game assets this project is built from.

## Status

Playable through all 11 scenes and the confirmed puzzle chain. Paco's
own sprite was never located in the original distribution (confirmed
absent, not merely unfound — see the wiki's Gap Analysis) and is
rendered as a placeholder marker pending that asset surfacing.

A parallel, ScummVM-native C++ engine skeleton (not yet buildable) is
tracked separately in [boolforge/scummvm](https://github.com/boolforge/scummvm),
`engines/paco1994/`.

## Running it yourself

```
pip install pygame numpy
python3 verify.py
```
