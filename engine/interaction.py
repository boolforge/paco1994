"""
interaction.py -- Per-scene interaction handlers implementing the confirmed
Puzzle Flag State Machine (P01-P08, see the companion wiki article).

Follows the "siloed logic" pattern: one handler per scene with special
logic; everything else falls through to a default (doors navigate
unconditionally, objects are inert).
"""
from __future__ import annotations
from .formats import AldScene, AldObject
from .game_data import (GameState, fire_dialogue,
                         FLAG_DOOR_OPEN, FLAG_SWITCH_USED, FLAG_MET_MARIANO,
                         FLAG_GAVE_FOOD, FLAG_READ_BOOK, ITEM_FOOD, ITEM_BOOK)


class Engine:
    """Forward-declared interface the handlers call back into.
    Implemented by engine.py's Paco1994Engine."""
    def transition_to_scene(self, dest_scene: str, dest_door: int, dest_pos: int) -> None: ...
    def show_dialogue(self, text: str, als_file: str | None) -> None: ...


def default_handle_door(obj: AldObject, state: GameState, eng: Engine) -> None:
    dest = obj.dest_scene.replace(".ALD", "").replace(".ald", "")
    eng.transition_to_scene(dest, obj.dest_door, obj.dest_pos)


def default_handle_object(obj_id: int, state: GameState, eng: Engine) -> None:
    pass  # inert by default


def scene2_3_handle_object(obj_id: int, state: GameState, eng: Engine) -> None:
    """Vending machine (disc-object) in scenes 2 and 3."""
    if not state.flags[4] and not state.has_item(ITEM_FOOD):  # FLAG_GOT_FOOD
        d = fire_dialogue("vending_machine", state)
        eng.show_dialogue(d.text_en, d.als_file)
    else:
        eng.show_dialogue("You already have enough food.", None)


def scene10_handle_object(obj_id: int, state: GameState, eng: Engine) -> None:
    if obj_id == 40:  # security switch
        if not state.flags[FLAG_SWITCH_USED]:
            d = fire_dialogue("security_door", state)
            eng.show_dialogue(d.text_en, d.als_file)
        else:
            eng.show_dialogue("The switch has already been activated.", None)


def scene10_handle_door(obj: AldObject, state: GameState, eng: Engine) -> None:
    if obj.obj_id == 39:  # blocked door to scene 9 (P01/P07)
        if state.flags[FLAG_DOOR_OPEN]:
            default_handle_door(obj, state, eng)
        elif state.has_item(ITEM_BOOK) and state.flags[FLAG_READ_BOOK]:
            d = fire_dialogue("guard_pass_1", state)  # P07: sets FLAG_DOOR_OPEN
            eng.show_dialogue(d.text_en, d.als_file)
        else:
            d = fire_dialogue("blocked_door", state)  # P01
            eng.show_dialogue(d.text_en, d.als_file)
    else:
        default_handle_door(obj, state, eng)  # obj 41: always passable


def scene11_handle_object(obj_id: int, state: GameState, eng: Engine) -> None:
    if obj_id != 43:
        return
    if not state.flags[FLAG_MET_MARIANO]:
        d = fire_dialogue("greet_mariano", state)
        eng.show_dialogue(d.text_en, d.als_file)
    elif state.has_item(ITEM_FOOD) and not state.flags[FLAG_GAVE_FOOD]:
        d = fire_dialogue("mariano_book", state)  # P06
        eng.show_dialogue(d.text_en, d.als_file)
    elif state.has_item(ITEM_BOOK) and not state.flags[FLAG_READ_BOOK]:
        d = fire_dialogue("paco_reads_book", state)
        eng.show_dialogue(d.text_en, d.als_file)
    else:
        d = fire_dialogue("greet_mariano", state)
        eng.show_dialogue(d.text_en, d.als_file)


# Scene ID -> (object_handler, door_handler)
SCENE_HANDLERS = {
    "2": (scene2_3_handle_object, default_handle_door),
    "3": (scene2_3_handle_object, default_handle_door),
    "10": (scene10_handle_object, scene10_handle_door),
    "11": (scene11_handle_object, default_handle_door),
}


def dispatch_click(x: int, y: int, scene: AldScene, state: GameState, eng: Engine) -> bool:
    """Hit-test all objects in scene order (matches original _comprueba1
    loop order). Returns True if a hotspot was hit."""
    obj_handler, door_handler = SCENE_HANDLERS.get(
        state.scene_id, (default_handle_object, default_handle_door))
    for obj in scene.objects:
        if obj.contains(x, y):
            if obj.is_door:
                door_handler(obj, state, eng)
            else:
                obj_handler(obj.obj_id, state, eng)
            return True
    return False
