"""Blueprint graphs for the server patch panel and its mouse interaction."""

from club_rules import rand, within
from club_screen import AMBER, MUTED, OVERLAY, TEAL, panel, rect, rgb, scale, text, words

COLORS = tuple(map(rgb, ("FF4866", "55BFFF", "FFD15F", "DC7AFF")))
PORTS = len(COLORS)
LEFT, RIGHT = 291, 709
FIRST_Y, ROW_HEIGHT = 219, 70
CLOSE_X, CLOSE_Y = 749, 121
PC_CLASS = "/Script/Engine.PlayerController"
WIDGETS = "/Script/UMG.WidgetBlueprintLibrary."
WIRE_INT_DEFAULTS = dict(WireShift=1, WireSelected=-1, WireCount=0)
WIRE_REAL_DEFAULTS = dict(WireMouseX=-1.0, WireMouseY=-1.0, MouseOriginX=0.0, MouseOriginY=0.0)
WIRE_BOOL_DEFAULTS = dict(RepairOpen=False, WireMismatch=False)


def cursor_mode(g):
    controller = g.invoke("HUD.GetOwningPlayerController", result="ReturnValue")
    shown = g.get("Shown")
    g.set("bShowMouseCursor", shown, class_path=PC_CLASS, target=controller)
    hidden = g.branch(shown)
    g.invoke(WIDGETS + "SetInputMode_GameAndUIEx", PlayerController=controller, InMouseLockMode="DoNotLock",
             bHideCursorDuringCapture=False)
    g.resume(hidden)
    g.invoke(WIDGETS + "SetInputMode_GameOnly", PlayerController=controller)


def open_repair(g):
    g.guard(g.negate(g.get("RepairOpen")))
    g.resize("WireConnected", PORTS)
    for color in range(PORTS):
        g.store("WireConnected", color, 0)
    g.set("WireShift", rand(g, 1, PORTS - 1))
    g.set("WireCount", 0)
    g.set("WireSelected", -1)
    g.set("WireMismatch", False)
    g.set("RepairOpen", True)
    g.call("SetRepairCursor", Shown=True)


def close_repair(g):
    g.guard(g.get("RepairOpen"))
    g.set("RepairOpen", False)
    g.set("WireSelected", -1)
    g.call("SetRepairCursor", Shown=False)


def target_row(g, color):
    return g.mod(g.add(color, g.get("WireShift")), PORTS)


def row_y(g, row):
    return g.math("Conv_IntToDouble", InInt=g.add(FIRST_Y, g.mul(row, ROW_HEIGHT)))


def port_at_cursor(g):
    column = g.get("Column")
    outside = g.branch(within(g, g.get("WireMouseX"), column, 34.0))
    for row in range(PORTS):
        other = g.branch(within(g, g.get("WireMouseY"), float(FIRST_Y + ROW_HEIGHT * row), 24.0))
        g.ret(row)
        g.resume(other)
    g.ret(-1)
    g.resume(outside)
    g.ret(-1)


def choose_port(g):
    port = g.get("Port")
    g.guard(g.gt(port, -1))
    g.guard(g.eq(g.arr("WireConnected", port), 0))
    g.set("WireSelected", port)
    g.set("WireMismatch", False)


def connect_wire(g):
    selected, row = g.get("WireSelected"), g.get("Row")
    g.guard(g.both(g.get("RepairOpen"), g.eq(g.get("ServerDown"), 1)))
    g.guard(g.both(g.gt(selected, -1), g.lt(selected, PORTS)))
    g.guard(g.both(g.gt(row, -1), g.lt(row, PORTS)))
    incorrect = g.branch(g.eq(target_row(g, selected), row))
    g.guard(g.eq(g.arr("WireConnected", selected), 0))
    g.store("WireConnected", selected, 1)
    g.set("WireCount", g.add(g.get("WireCount"), 1))
    g.guard(g.eq(g.get("WireCount"), PORTS))
    g.set("ServerDown", 0)
    g.set("Cash", g.add(g.get("Cash"), 100))
    g.call("SyncServerAlarm")
    g.call("CloseRepair")
    g.resume(incorrect)
    g.set("WireMismatch", True)


def release_wire(g):
    row = g.get("Row")
    g.guard(g.gt(row, -1))
    g.call("ConnectWire", Row=row)
    g.set("WireSelected", -1)


def read_panel_pointer(g):
    controller = g.invoke("HUD.GetOwningPlayerController", result="ReturnValue")
    x, y, valid = g.invoke("PlayerController.GetMousePosition", target=controller,
                           result=("LocationX", "LocationY", "ReturnValue"))
    ui_scale = g.math("FMax", A=g.get("UiScale"), B=0.01)
    for member, coordinate, origin in (("WireMouseX", x, "MouseOriginX"), ("WireMouseY", y, "MouseOriginY")):
        logical = g.div(g.sub(coordinate, g.get(origin), True), ui_scale, True)
        g.set(member, g.choose(valid, logical, -1.0, "Float"))


def repair_input(g):
    g.call("ReadPanelPointer")
    pressed = g.key("LeftMouseButton", just_pressed=True)
    close_click = g.both(within(g, g.get("WireMouseX"), CLOSE_X, 23.0),
                         within(g, g.get("WireMouseY"), CLOSE_Y, 23.0))
    stay = g.branch(g.either(g.key("Q", just_pressed=True), g.both(pressed, close_click)))
    g.call("CloseRepair")
    g.resume(stay)
    release = g.branch(pressed)
    port = g.call("WirePortAtCursor", result="Value", Column=float(LEFT))
    g.call("ChooseWirePort", Port=port)
    row = g.call("WirePortAtCursor", result="Value", Column=float(RIGHT))
    g.call("ReleaseWire", Row=row)
    # A click on the left can also select a wire for a second click on the right.
    outside = g.both(g.lt(port, 0), g.lt(row, 0))
    g.guard(outside)
    g.set("WireSelected", -1)
    g.resume(release)
    controller = g.invoke("HUD.GetOwningPlayerController", result="ReturnValue")
    g.guard(g.invoke("PlayerController.WasInputKeyJustReleased", target=controller,
                     result="ReturnValue", Key="LeftMouseButton"))
    row = g.call("WirePortAtCursor", result="Value", Column=float(RIGHT))
    g.call("ReleaseWire", Row=row)


def wire_line(g, x1, y1, x2, y2, color, thickness):
    sx1, sx2 = (g.add(g.get("OriginX"), scale(g, x), True) for x in (x1, x2))
    sy1, sy2 = (g.add(g.get("OriginY"), scale(g, y), True) for y in (y1, y2))
    g.invoke("HUD.DrawLine", StartScreenX=sx1, StartScreenY=sy1, EndScreenX=sx2,
             EndScreenY=sy2, LineColor=color, LineThickness=scale(g, thickness))


def cable(g, start, end_x, end_y, color):
    for tint, thickness in ((rgb("090B0E"), 14.0), (color, 7.0)):
        wire_line(g, LEFT + 16, start, 342, start, tint, thickness)
        wire_line(g, 342, start, end_x, end_y, tint, thickness)


def draw_connected(g):
    selected = g.get("Color")
    connected = g.branch(g.eq(g.arr("WireConnected", selected), 1))
    y = row_y(g, target_row(g, selected))
    start = row_y(g, selected)
    tint = g.get("Tint")
    cable(g, start, RIGHT - 52, y, tint)
    wire_line(g, RIGHT - 52, y, RIGHT - 16, y, rgb("090B0E"), 14.0)
    wire_line(g, RIGHT - 52, y, RIGHT - 16, y, tint, 7.0)
    g.resume(connected)
    g.guard(g.eq(g.get("WireSelected"), selected))
    x = g.clamp(g.get("WireMouseX"), 342.0, RIGHT - 16.0)
    y = g.clamp(g.get("WireMouseY"), 180.0, 469.0)
    cable(g, row_y(g, selected), x, y, tint)


def draw_port(g):
    x, y, tint = g.get("PortX"), g.get("PortY"), g.get("Tint")
    rect(g, g.sub(x, 22.0, True), g.sub(y, 15.0, True), 44, 30, rgb("060B11"))
    rect(g, g.sub(x, 18.0, True), g.sub(y, 10.0, True), 36, 20, tint)
    text(g, g.get("Code"), g.sub(x, 5.0, True), g.sub(y, 8.0, True), 0.8, rgb("15121B"))


def draw_repair(g):
    rect(g, 0, 0, 1000, 620, OVERLAY)
    panel(g, 217, 92, 566, 444)
    rect(g, 217, 92, 566, 4, rgb("FF4866"))
    text(g, "Панель ремонта сервера", 242, 111, 1.55)
    text(g, "Перетащи провод или нажми на два разъёма одного цвета.", 242, 151, 0.94, MUTED)
    rect(g, 730, 102, 38, 38, rgb("293E4F"))
    text(g, "×", 741, 104, 1.45)
    rect(g, 247, 183, 506, 281, rgb("11171C"))
    for x in (264, 682):
        rect(g, x, 186, 54, 275, rgb("34414D"))
    for color, tint in enumerate(COLORS):
        y = float(FIRST_Y + ROW_HEIGHT * color)
        wire_line(g, LEFT + 16, y, LEFT + 35, y, tint, 7.0)
        y = row_y(g, target_row(g, color))
        wire_line(g, RIGHT - 35, y, RIGHT - 16, y, tint, 7.0)
        g.call("DrawRepairCable", Color=color, Tint=tint)
    for color, tint in enumerate(COLORS):
        code = "ABCD"[color]
        g.call("DrawRepairPort", PortX=LEFT, PortY=FIRST_Y + ROW_HEIGHT * color, Code=code, Tint=tint)
        g.call("DrawRepairPort", PortX=RIGHT, PortY=row_y(g, target_row(g, color)), Code=code, Tint=tint)
    count = g.append("Соединено ", g.string(g.get("WireCount")), f" из {PORTS}")
    text(g, count, 247, 490, 1.0, TEAL)
    text(g, words(g, g.get("WireMismatch"), "Цвета не совпадают", ""), 425, 490, 0.95, AMBER)
    text(g, "Q  закрыть", 663, 490, 0.95, MUTED)


WIRE_GRAPHS = (
    ("OpenRepair", open_repair, ()), ("CloseRepair", close_repair, ()),
    ("SetRepairCursor", cursor_mode, (("Shown", "bool"),)),
    ("ReadPanelPointer", read_panel_pointer, ()),
    ("RepairInput", repair_input, ()),
    ("WirePortAtCursor", port_at_cursor, (("Column", "real"),), "int"),
    ("ChooseWirePort", choose_port, (("Port", "int"),)),
    ("ConnectWire", connect_wire, (("Row", "int"),)),
    ("ReleaseWire", release_wire, (("Row", "int"),)),
    ("DrawRepair", draw_repair, ()),
    ("DrawRepairCable", draw_connected, (("Color", "int"), ("Tint", "color"))),
    ("DrawRepairPort", draw_port, (("PortX", "real"), ("PortY", "real"), ("Code", "string"), ("Tint", "color"))),
)
