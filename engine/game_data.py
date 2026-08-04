"""
game_data.py -- Confirmed game state, dialogue database, and puzzle logic
for Paco El Hare vs Los Marcianos Siderales (1994).

All data below is either directly extracted from the real HARE.EXE binary
(dialogue text, VOC filenames, hex offsets) or confirmed by direct
disassembly (field counts, save format, main-loop structure). See the
companion wiki article's Dialogue Database and Puzzle Flag State Machine
sections for full sourcing.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Confirmed exact via disassembly of _graba_partida (reko-decomp.txt:3936-3995)
# ---------------------------------------------------------------------------
INVENTORY_SLOTS = 16
FLAG_SLOTS = 10

# Flag indices (order matches this project's puzzle-tree documentation;
# the *storage* size of 10 is confirmed, individual index->meaning bindings
# are this project's own consistent naming, not extracted symbol-by-symbol)
FLAG_DOOR_OPEN      = 0  # Scene 10->9 guard door unblocked
FLAG_SWITCH_USED    = 1  # Scene 10 security switch activated
FLAG_MET_MARIANO    = 2
FLAG_GAVE_FOOD      = 3
FLAG_GOT_FOOD       = 4
FLAG_GOT_BOOK       = 5
FLAG_READ_BOOK      = 6

ITEM_NONE  = 0
ITEM_FOOD  = 1
ITEM_BOOK  = 2


@dataclass
class DialogueEntry:
    text_es: str
    text_en: str
    als_file: str | None
    flag_set: int | None = None
    add_item: int = ITEM_NONE
    remove_item: int = ITEM_NONE


# 19 confirmed dialogue entries, hex offsets from HARE.EXE 0xC182-0xC624
DIALOGUES: dict[str, DialogueEntry] = {
    "blocked_door": DialogueEntry(
        "Lo siento, no te puedo dejar pasar.",
        "Sorry, I can't let you through.", "9.ALS"),
    "stuck_door": DialogueEntry(
        "Esta atascada. Necesitare algo para abrirla.",
        "It's stuck. I'll need something to open it.", "3.ALS"),
    "security_door": DialogueEntry(
        "Es una puerta de seguiridad. Debe haber un interruptor en algun sitio.",
        "It's a security door. There must be a switch somewhere around here.",
        "8.ALS", flag_set=FLAG_SWITCH_USED),
    "vending_machine": DialogueEntry(
        "Es una maquina expendedora de salchichas de humano.",
        "It's a human sausage vending machine.",
        "1.ALS", flag_set=FLAG_GOT_FOOD, add_item=ITEM_FOOD),
    "slot_look": DialogueEntry("Al loro!", "Heads up!", None),
    "slot_use": DialogueEntry(
        "Una maquina tragaperras!", "A slot machine!", "7.ALS"),
    "greet_mariano": DialogueEntry(
        "Que te pasa amigo mio, que te veo desolado?",
        "What's the matter, my friend? You look so down.",
        None, flag_set=FLAG_MET_MARIANO),
    "mariano_sad": DialogueEntry(
        "estoy triste porque mi vida no tiene sentido, y porque tengo hambre",
        "I'm sad because my life has no meaning. And because I'm hungry.",
        "5.ALS"),
    "mariano_book": DialogueEntry(
        "Tu ten karma, y leete este libro.",
        "You keep the karma, and read this book.",
        "2.ALS", flag_set=FLAG_GAVE_FOOD, add_item=ITEM_BOOK, remove_item=ITEM_FOOD),
    "paco_reads_book": DialogueEntry(
        "OH! En este libro aparecen nuevas teorias sobre donde esta la paz en el mundo!",
        "Oh! This book contains new theories about where world peace can be found!",
        "2.ALS", flag_set=FLAG_READ_BOOK),
    "thanks": DialogueEntry("muchas gracias!", "Thank you very much!", None),
    "guard_pass_1": DialogueEntry(
        "Has demostrado ser un gran amigo. Puedes pasar si quieres.",
        "You've proven yourself to be a great friend. You may pass if you like.",
        "13.ALS", flag_set=FLAG_DOOR_OPEN),
    "give_food_1": DialogueEntry("Toma machote.", "Here you go, pal.", "14.ALS"),
    "refuse_food": DialogueEntry(
        "No gracias. No me gusta el chopped",
        "No thanks. I don't like processed meat.", "6.ALS"),
    "give_food_2": DialogueEntry("Toma machote.", "Here you go, pal.", "11.ALS"),
    "accept_food": DialogueEntry(
        "Gracias. Enseguida me lo como.",
        "Thanks. I'll eat it right away.", "6.ALS"),
    "guard_pass_2": DialogueEntry(
        "Has demostrado ser un gran amigo. Puedes pasar si quieres.",
        "You've proven yourself to be a great friend. You may pass if you like.",
        "12.ALS"),
    "give_food_final": DialogueEntry("Toma machote.", "Here you go, pal.", "14.ALS"),
    "save_done": DialogueEntry(
        "Acabas de grabar la partida, tio.",
        "You just saved your game, dude.", None),
}


@dataclass
class GameState:
    """Full mutable game state. Save/load mirrors the confirmed real format:
    plain text, 4 fixed fields + 16-slot inventory loop + 10-slot flag loop
    + 2 fixed fields (see _graba_partida disassembly in the wiki)."""
    scene_id: str = "1"
    hare_x: int = 160
    hare_y: int = 170
    facing_right: bool = True
    inventory: list[int] = field(default_factory=lambda: [ITEM_NONE] * INVENTORY_SLOTS)
    flags: list[bool] = field(default_factory=lambda: [False] * FLAG_SLOTS)
    dialogue_active: bool = False
    dialogue_text: str = ""

    def has_item(self, item: int) -> bool:
        return item in self.inventory

    def add_item(self, item: int) -> None:
        for i, slot in enumerate(self.inventory):
            if slot == ITEM_NONE:
                self.inventory[i] = item
                return

    def remove_item(self, item: int) -> None:
        for i, slot in enumerate(self.inventory):
            if slot == item:
                self.inventory[i] = ITEM_NONE
                return

    def save_text(self) -> str:
        """Serialize in the CONFIRMED real plain-text format (no XOR)."""
        lines = [self.scene_id + ".ALD", "0", "64",
                 str(self.hare_x), str(self.hare_y)]
        lines += [str(v) for v in self.inventory]   # 16-slot loop
        lines += ["1" if f else "0" for f in self.flags]  # 10-slot loop
        lines += ["0", "0"]
        return "\r\n".join(lines) + "\r\n"

    @classmethod
    def load_text(cls, text: str) -> "GameState":
        lines = [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]
        gs = cls()
        gs.scene_id = lines[0].replace(".ALD", "")
        gs.hare_x = int(lines[3]); gs.hare_y = int(lines[4])
        gs.inventory = [int(x) for x in lines[5:5+INVENTORY_SLOTS]]
        gs.flags = [x == "1" for x in lines[5+INVENTORY_SLOTS:5+INVENTORY_SLOTS+FLAG_SLOTS]]
        return gs


def fire_dialogue(key: str, state: GameState) -> DialogueEntry:
    """Apply a dialogue's state mutations and return it for display/audio."""
    d = DIALOGUES[key]
    if d.remove_item != ITEM_NONE:
        state.remove_item(d.remove_item)
    if d.add_item != ITEM_NONE:
        state.add_item(d.add_item)
    if d.flag_set is not None:
        state.flags[d.flag_set] = True
    return d
