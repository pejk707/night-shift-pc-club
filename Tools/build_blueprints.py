"""Run in Unreal Editor 5.8 to author the prototype's Blueprint assets."""

from math import exp, pi, sin
from pathlib import Path
from struct import pack
import sys
import traceback
import wave

import unreal

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from blueprint_graph import EDIT, LIB, Graph, pin, pin_type
from club_guests import GUEST_ACTOR_ARRAYS, GUEST_GRAPHS, GUEST_VECTOR_ARRAYS, RESET_INTS
from club_rules import (
    BELL_PATH, BOOL_DEFAULTS, DESK_ARRAYS, INT_DEFAULTS, LINE_ARRAYS, REAL_DEFAULTS, RULE_GRAPHS, SCENE_ARRAYS,
    start_simulation,
)
from club_screen import SCREEN_GRAPHS
from club_menu import MENU_GRAPHS, MENU_INT_DEFAULTS
from club_service import MICROWAVE_SOUND, SERVICE_GRAPHS, SERVICE_INT_DEFAULTS
from club_wires import WIRE_BOOL_DEFAULTS, WIRE_GRAPHS, WIRE_INT_DEFAULTS, WIRE_REAL_DEFAULTS

ASSET_ROOT = "/Game/NightShift"
HUD_PATH = ASSET_ROOT + "/Blueprints/BP_ClubHUD"
MODE_PATH = ASSET_ROOT + "/Blueprints/BP_Shift"
MAP_PATH = ASSET_ROOT + "/Maps/L_Club"
LOG_PATH = TOOLS_DIR.parent / "Saved" / "NightShiftBlueprintBuild.txt"


def log(message):
    unreal.log(message)
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def require(value, message):
    if not value:
        raise RuntimeError(message)
    return value


def import_signal(path, duration, tones, volume):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return
    folder, name = path.rsplit("/", 1)
    filename = LOG_PATH.parent / (name + ".wav")
    filename.parent.mkdir(exist_ok=True)
    sample_rate = 44100
    samples = bytearray()
    for frame in range(int(duration * sample_rate)):
        time = frame / sample_rate
        amplitude = 0.0
        for start, pitch in tones:
            age = time - start
            if age < 0:
                continue
            envelope = min(age / 0.006, 1.0) * exp(-12 * age)
            amplitude += envelope * (sin(2 * pi * pitch * age) + 0.24 * sin(2 * pi * pitch * 2.76 * age))
        fade_out = min((duration - time) / 0.04, 1.0)
        samples.extend(pack("<h", round(volume * amplitude * fade_out)))
    with wave.open(str(filename), "wb") as sound:
        sound.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        sound.writeframes(samples)
    task = unreal.AssetImportTask()
    task.filename = str(filename)
    task.destination_path = folder
    task.automated = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    require(unreal.EditorAssetLibrary.does_asset_exist(path), f"Could not import {name}")


def create_hud(save=True):
    import_signal(BELL_PATH, 0.6, ((0, 1046.5), (0.12, 784.0)), 11000)
    import_signal(MICROWAVE_SOUND, 0.48, ((0, 1568.0), (0.2, 1568.0)), 7800)
    bp = require(LIB.create_blueprint_asset_with_parent(HUD_PATH, unreal.HUD), "Could not create BP_ClubHUD")
    events = EDIT.get_graph_editor_by_name(bp, "EventGraph")
    for type_name, defaults in (
        ("int", INT_DEFAULTS | WIRE_INT_DEFAULTS | SERVICE_INT_DEFAULTS | MENU_INT_DEFAULTS),
        ("real", REAL_DEFAULTS | WIRE_REAL_DEFAULTS),
        ("bool", BOOL_DEFAULTS | WIRE_BOOL_DEFAULTS),
        ("int[]", dict.fromkeys(DESK_ARRAYS + LINE_ARRAYS + ("WireConnected",) + tuple(RESET_INTS), "")),
        ("real[]", dict.fromkeys(SCENE_ARRAYS, "")),
        ("vector[]", dict.fromkeys(("PcStatusAnchors",) + GUEST_VECTOR_ARRAYS, "")),
        ("actor[]", dict.fromkeys(GUEST_ACTOR_ARRAYS, "")),
        ("widget", {"ClubMenuWidget": "None"}),
    ):
        kind = pin_type(type_name)
        for name, value in defaults.items():
            literal = str(value).lower() if isinstance(value, bool) else str(value)
            require(events.add_member_variable(name, kind, literal), f"Could not add variable {name}")

    writers = []
    graphs = RULE_GRAPHS + SCREEN_GRAPHS + WIRE_GRAPHS + SERVICE_GRAPHS + GUEST_GRAPHS + MENU_GRAPHS
    for name, writer, params, *result in graphs:
        graph = Graph(require(EDIT.create_and_edit_function_graph(bp, name), f"Could not create {name}"))
        for param, kind in params:
            require(graph.editor.add_graph_input_parameter(param, pin_type(kind)).is_valid(), f"Could not add {name}.{param}")
        if result:
            graph.first_result = require(graph.editor.add_graph_output_parameter("Value", pin_type(result[0])),
                                         f"Could not add {name}.Value")
        graph.cursor = graph.editor.find_graph_entry_pin()
        entry = graph.cursor.get_owning_node()
        graph.params = {param: pin(entry, param, True) for param, _ in params}
        writers.append((name, graph, writer))

    require(LIB.compile_blueprint(bp), "Could not compile the Blueprint's function signatures")
    for name, graph, writer in writers:
        log("Generating " + name)
        # Signature updates may reconstruct pins. Resolve each entry again.
        graph.cursor = graph.editor.find_graph_entry_pin()
        entry = graph.cursor.get_owning_node()
        graph.params = {param: pin(entry, param, True) for param in graph.params}
        writer(graph)

    for name, x, y, actions in (
        ("ReceiveBeginPlay", 0, 0, start_simulation),
        ("ReceiveTick", 0, 520,
         lambda g: g.call("PlayerTick", FrameSeconds=pin(g.cursor.get_owning_node(), "DeltaSeconds", True))),
        ("ReceiveDrawHUD", 0, 1040,
         lambda g: g.call("DrawFrame", Width=pin(g.cursor.get_owning_node(), "SizeX", True),
                          Height=pin(g.cursor.get_owning_node(), "SizeY", True))),
    ):
        event = events.find_event_node(name) or LIB.add_event_override(bp, name, unreal.IntPoint(x, y))
        require(event, f"Could not find or add {name}")
        event.set_node_pos(unreal.IntPoint(x, y))
        graph = Graph(events)
        graph.cursor = event.find_then_pin()
        actions(graph)
        graph.cursor.get_owning_node().set_node_pos(unreal.IntPoint(x + 310, y))

    if not LIB.compile_blueprint(bp):
        for name, graph, _ in writers:
            for node in graph.editor.list_nodes_with_errors():
                log(f"Error in {name}: {node.get_node_title()}")
        raise RuntimeError("BP_ClubHUD failed to compile. See the Unreal Output Log.")
    if save:
        require(unreal.EditorAssetLibrary.save_loaded_asset(bp, False), "Could not save BP_ClubHUD")
    return bp


def configure_mode(bp, hud):
    events = EDIT.get_graph_editor_by_name(bp, "EventGraph")
    event = events.find_event_node("ReceiveBeginPlay")
    if not event:
        event = LIB.add_event_override(bp, "ReceiveBeginPlay", unreal.IntPoint(0, 0))
    graph = Graph(events)
    graph.cursor = event.find_then_pin()
    controller = graph.invoke("GameplayStatics.GetPlayerController", result="ReturnValue", PlayerIndex=0)
    graph.invoke("PlayerController.ClientSetHUD", target=controller,
                 NewHUDClass=hud.generated_class().get_path_name())
    require(LIB.compile_blueprint(bp), "BP_Shift failed to compile")
    require(unreal.EditorAssetLibrary.save_loaded_asset(bp, False), "Could not save BP_Shift")


def create_mode(hud):
    bp = require(LIB.create_blueprint_asset_with_parent(MODE_PATH, unreal.GameModeBase), "Could not create BP_Shift")
    configure_mode(bp, hud)
    return bp


def create_level():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    require(levels.new_level(MAP_PATH), "Could not create L_Club")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(0, 0, 120)), "Could not place PlayerStart")
    require(levels.save_current_level(), "Could not save L_Club")


def main():
    present = [path for path in (HUD_PATH, MODE_PATH, MAP_PATH) if unreal.EditorAssetLibrary.does_asset_exist(path)]
    if present:
        raise RuntimeError("These assets already exist. Generate in a clean copy to preserve edits: " + ", ".join(present))
    create_mode(create_hud())
    create_level()
    log("Night Shift Blueprint assets compiled and saved.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise
