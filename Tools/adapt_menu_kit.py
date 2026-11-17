"""Localize the imported Minimal Menu Kit and route its buttons to the club HUD."""

import re
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).parent))

from blueprint_graph import ARRAY, Graph
from club_menu import GO_MAIN, HELP, KIT_COMMANDS, OPTIONS, PLAY, QUIT, RESUME, menu_tags


def adapt_style():
    blueprint = unreal.load_asset("/Game/UI/UIS_Button")
    style = unreal.get_default_object(blueprint.generated_class())
    style.modify()
    style.set_editor_property("min_width", 260)
    style.set_editor_property("min_height", 43)
    for names, color in (
        (("normal_base", "selected_base"), (0.046, 0.089, 0.145, 1.0)),
        (("normal_hovered", "selected_hovered"), (0.066, 0.270, 0.330, 1.0)),
        (("normal_pressed", "selected_pressed"), (0.086, 0.402, 0.427, 1.0)),
    ):
        tint = unreal.SlateColor(specified_color=unreal.LinearColor(*color))
        for name in names:
            brush = style.get_editor_property(name)
            brush.set_editor_property("tint_color", tint)
            style.set_editor_property(name, brush)
    if not unreal.EditorAssetLibrary.save_loaded_asset(blueprint, False):
        raise RuntimeError("Couldn't save UIS_Button")


def adapt_menu(name, title, buttons, hidden):
    blueprint = unreal.load_asset(f"/Game/UI/{name}")
    if blueprint is None:
        raise RuntimeError(f"Missing menu widget {name}")
    editor = unreal.BlueprintGraphEditor.get_graph_editor_by_name(blueprint, "EventGraph")
    events = [node for node in editor.list_all_nodes()
              if node.get_class().get_name() == "K2Node_ComponentBoundEvent"]
    editor.remove_nodes([node for node in editor.list_all_nodes() if node not in events])
    known_nodes = {node.get_name() for node in events}
    for event in events:
        match = re.search(r"\((btn\w+)\)", str(event.get_node_title()))
        if not match:
            continue
        output = event.find_then_pin()
        button = buttons.get(match[1])
        if button:
            graph = Graph(editor)
            origin = event.get_node_pos()
            graph.cursor = output
            player = graph.invoke("GameplayStatics.GetPlayerController", result="ReturnValue", PlayerIndex=0)
            hud = graph.invoke("PlayerController.GetHUD", result="ReturnValue", target=player)
            graph.invoke(ARRAY + "Array_AddUnique", TargetArray=menu_tags(graph, hud),
                         NewItem=KIT_COMMANDS[button[0]])
            for node in editor.list_all_nodes():
                if node.get_name() in known_nodes or node == event:
                    continue
                location = node.get_node_pos()
                node.set_node_pos(unreal.IntPoint(origin.x + 290 + location.x, origin.y + location.y - 440))
            known_nodes = {node.get_name() for node in editor.list_all_nodes()}

    prefix = f"/Game/UI/{name}.{name}:WidgetTree."
    widgets = {widget.get_name(): widget for widget in unreal.ObjectIterator(unreal.Widget)
               if widget.get_path_name().startswith(prefix)}
    widgets["lblTitle"].modify()
    widgets["lblTitle"].set_editor_property("text", title)
    for button, (_, label) in buttons.items():
        widgets[button].modify()
        widgets[button].set_editor_property("text", label)
    for widget in hidden:
        widgets[widget].modify()
        widgets[widget].set_editor_property("visibility", unreal.SlateVisibility.COLLAPSED)

    if not unreal.BlueprintEditorLibrary.compile_blueprint(blueprint):
        raise RuntimeError(f"Couldn't compile {name}")
    if not unreal.EditorAssetLibrary.save_loaded_asset(blueprint, False):
        raise RuntimeError(f"Couldn't save {name}")


def adapt_menu_kit():
    adapt_style()
    adapt_menu("UI_MainMenu", "Ночная смена", {
        "btnNewGame": (PLAY, "Начать игру"),
        "btnSettings": (OPTIONS, "Настройки"),
        "btnCredits": (HELP, "Управление"),
        "btnQuit": (QUIT, "Выйти"),
    }, ("btnContinue", "Spacer_117"))
    adapt_menu("UI_Pause", "Пауза", {
        "btnReturn": (RESUME, "Продолжить"),
        "btnSettings": (OPTIONS, "Настройки"),
        "btnExit": (GO_MAIN, "Главное меню"),
    }, ("btnBack",))


if __name__ == "__main__":
    adapt_menu_kit()
