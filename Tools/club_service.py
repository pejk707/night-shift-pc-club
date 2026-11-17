"""Generate the fridge, microwave, and local PC recovery Blueprint graphs."""

from club_rules import (
    COLD, CRASH, DRINK, DRINK_NAMES, DRINK_PANEL, GAME_FROZEN, HEATING, HOT, I, NONE, NO_SERVICE_PANEL,
    NO_SLICE, PC_PANEL, REPAIR_KIT, SLICE, SUPPLIES_NIGHT, ceil_div, max_int, upgrade_effect, within,
)
from club_screen import (
    AMBER, BLUE, CARD, INSET, MUTED, PINK, RAIL, TEAL, VIOLET, WHITE,
    color_when, drink_label, keycap, modal_surface, rect, rgb, surface, text, words,
)

MICROWAVE_SOUND = "/Game/NightShift/Audio/S_MicrowaveReady"
HEAT_TICKS, HOT_TICKS, REHEAT_TICKS = 100, 220, 40
BOOT_TICKS = 12
END_GAME, RESTART_LAUNCHER, START_GAME = range(1, 4)
RETURN_CAN = 4
SERVICE_INT_DEFAULTS = dict(ServicePanel=NO_SERVICE_PANEL, ServicePc=-1, ServiceHint=0, HeldDrink=0,
                            MicrowaveState=NO_SLICE, MicrowaveAt=0)
CLOSE = (749, 152, 36, 34)
FRIDGE_BUTTONS = tuple((330 + 170 * index, 286, 146, 124) for index in range(len(DRINK_NAMES)))
RETURN_BUTTON = (500, 423, 290, 46)
PC_BUTTONS = tuple((500, 252 + 66 * index, 454, 53) for index in range(3))
CAN_TINTS = (AMBER, VIOLET, BLUE)
KEYS = ("One", "Two", "Three", "Four")


def close_service_panel(g):
    g.guard(g.gt(g.get("ServicePanel"), NO_SERVICE_PANEL))
    g.set("ServicePanel", NO_SERVICE_PANEL)
    g.set("ServicePc", -1)
    g.set("ServiceHint", 0)
    g.call("SetRepairCursor", Shown=False)


def reset_service(g):
    g.call("CloseServicePanel")
    g.set("HeldDrink", 0)
    g.set("MicrowaveState", NO_SLICE)
    g.set("MicrowaveAt", 0)


def open_fridge(g):
    item = g.get("HeldItem")
    g.guard(g.either(g.eq(item, NONE), g.eq(item, DRINK)))
    g.set("ServicePanel", DRINK_PANEL)
    g.call("SetRepairCursor", Shown=True)


def open_pc(g):
    g.set("ServicePc", g.get("Desk"))
    g.set("ServiceHint", 0)
    g.set("ServicePanel", PC_PANEL)
    g.call("SetRepairCursor", Shown=True)


def choose_drink(g):
    choice = g.get("Choice")
    pick = g.branch(g.eq(choice, RETURN_CAN))
    g.guard(g.eq(g.get("HeldItem"), DRINK))
    g.set("HeldItem", NONE)
    g.call("CloseServicePanel")
    g.resume(pick)
    g.guard(g.both(g.gt(choice, 0), g.lt(choice, RETURN_CAN)))
    g.set("HeldDrink", g.sub(choice, 1))
    g.set("HeldItem", DRINK)
    g.call("CloseServicePanel")


def choose_pc_action(g):
    desk, choice = g.get("Desk"), g.get("Choice")
    g.guard(g.eq(g.arr("DeskState", desk), CRASH))
    g.guard(g.eq(g.arr("RestartUntil", desk), 0))
    stopped = g.branch(g.eq(g.arr("RecoveryStage", desk), 0))
    frozen_game = g.eq(g.arr("RequestVariant", desk), GAME_FROZEN)
    need = g.choose(frozen_game, END_GAME, RESTART_LAUNCHER)
    matched = g.branch(g.eq(choice, need))
    g.store("RecoveryStage", desk, 1)
    g.set("ServiceHint", 0)
    g.resume(matched)
    g.set("ServiceHint", need)
    g.resume(stopped)
    other = g.branch(g.eq(choice, START_GAME))
    cut = g.sub(100, upgrade_effect(g, REPAIR_KIT))
    boot = ceil_div(g, g.mul(BOOT_TICKS, cut), 100)
    g.store("RestartUntil", desk, g.add(g.get("Step"), boot))
    g.set("ServiceHint", 0)
    g.resume(other)
    g.set("ServiceHint", START_GAME)


def finish_pc_recovery(g):
    desk = g.get("Desk")
    deadline = g.arr("RestartUntil", desk)
    g.guard(g.both(g.gt(deadline, 0), g.negate(g.lt(g.get("Step"), deadline))))
    g.call("CloseOrder", Desk=desk, Reward=45)
    g.guard(g.eq(g.get("ServicePc"), desk))
    g.call("CloseServicePanel")


def use_microwave(g):
    g.guard(g.negate(g.lt(g.get("ShiftNo"), SUPPLIES_NIGHT)))
    state = g.get("MicrowaveState")
    waiting = g.branch(g.eq(state, HOT))
    g.guard(g.eq(g.get("HeldItem"), NONE))
    g.set("HeldItem", SLICE)
    g.set("MicrowaveState", NO_SLICE)
    g.set("MicrowaveAt", 0)
    g.resume(waiting)
    g.guard(g.negate(g.eq(state, HEATING)))
    heat = g.choose(g.eq(state, COLD), REHEAT_TICKS, HEAT_TICKS)
    g.set("MicrowaveAt", g.add(g.get("Step"), heat))
    g.set("MicrowaveState", HEATING)


def advance_microwave(g):
    g.guard(g.gt(g.get("MicrowaveAt"), 0))
    g.guard(g.negate(g.lt(g.get("Step"), g.get("MicrowaveAt"))))
    done = g.branch(g.eq(g.get("MicrowaveState"), HEATING))
    g.set("MicrowaveState", HOT)
    g.set("MicrowaveAt", g.add(g.get("Step"), HOT_TICKS))
    g.invoke("GameplayStatics.PlaySound2D", Sound=MICROWAVE_SOUND + ".S_MicrowaveReady",
             VolumeMultiplier=0.7, bIsUISound=True)
    g.resume(done)
    g.set("MicrowaveState", COLD)
    g.set("MicrowaveAt", 0)


def pointer_hit(g, dimensions):
    x, y, w, h = dimensions
    return g.both(within(g, g.get("WireMouseX"), float(x), w / 2),
                  within(g, g.get("WireMouseY"), float(y), h / 2))


def process_choice(g):
    fridge = g.branch(g.eq(g.get("ServicePanel"), DRINK_PANEL))
    g.call("ChooseDrink", Choice=g.get("Choice"))
    g.resume(fridge)
    g.call("ChoosePcAction", Desk=g.get("ServicePc"), Choice=g.get("Choice"))


def service_input(g):
    mouse = g.key("LeftMouseButton", just_pressed=True)
    g.call("ReadPanelPointer")
    stay = g.branch(g.either(g.key("Q", just_pressed=True), g.both(mouse, pointer_hit(g, CLOSE))))
    g.call("CloseServicePanel")
    g.resume(stay)
    fridge = g.eq(g.get("ServicePanel"), DRINK_PANEL)
    target = max_int(g, 0, g.get("ServicePc"))
    active_pc = g.eq(g.arr("DeskState", target), CRASH)
    pc_ok = g.branch(g.both(g.negate(fridge), g.negate(active_pc)))
    g.call("CloseServicePanel")
    g.resume(pc_ok)
    choice = 0
    for index, fridge_box in enumerate(FRIDGE_BUTTONS + (RETURN_BUTTON,)):
        fridge_hit = g.both(fridge, pointer_hit(g, fridge_box))
        if index < len(PC_BUTTONS):
            pc_hit = g.both(g.negate(fridge), pointer_hit(g, PC_BUTTONS[index]))
            box_hit = g.either(fridge_hit, pc_hit)
            key = g.key(KEYS[index], just_pressed=True)
        else:
            box_hit = fridge_hit
            key = g.both(fridge, g.key(KEYS[index], just_pressed=True))
        choice = g.choose(g.either(key, g.both(mouse, box_hit)), index + 1, choice)
    g.guard(g.gt(choice, 0))
    g.call("ProcessServiceChoice", Choice=choice)


def service_shell(g, title, subtitle, color):
    modal_surface(g, 218, 122, 564, 373, color)
    text(g, title, 247, 142, 1.9)
    text(g, subtitle, 247, 183, 1.03, MUTED)
    x, y, w, h = CLOSE
    surface(g, x - w / 2, y - h / 2, w, h, stroke=color_when(g, pointer_hit(g, CLOSE), color, RAIL))
    text(g, "×", x - 7, y - 16, 1.32, WHITE)
    keycap(g, "Q", 663, 463, 22)
    text(g, "Закрыть", 693, 464, 0.95, MUTED)


def service_button(g, box, key, title, *, tint=TEAL, enabled=True):
    x, y, w, h = box
    hover = g.both(enabled, pointer_hit(g, box))
    left, top = x - w / 2, y - h / 2
    surface(g, left, top, w, h, stroke=color_when(g, hover, tint, RAIL),
            face=color_when(g, enabled, CARD, INSET))
    keycap(g, key, left + 13, y - 10.0)
    text(g, title, left + 47, y - 10, 1.12, color_when(g, enabled, WHITE, MUTED))


def draw_fridge(g):
    service_shell(g, "Холодильник", "Возьми энергетик, который попросил клиент.", BLUE)
    for index, (name, box, tint) in enumerate(zip(DRINK_NAMES, FRIDGE_BUTTONS, CAN_TINTS), 1):
        x, y, w, h = box
        border = color_when(g, pointer_hit(g, box), tint, RAIL)
        surface(g, x - w / 2, y - h / 2, w, h, stroke=border, face=INSET)
        rect(g, x - 13, y - 42, 26, 54, tint)
        rect(g, x - 10, y - 45, 20, 4, rgb("A6C0CB"))
        rect(g, x - 13, y - 23, 26, 16, rgb("112139"))
        keycap(g, str(index), x - w / 2 + 11, y + 29, tint=tint)
        text(g, name, x - w / 2 + 42, y + 29, 1.03)
    g.guard(g.eq(g.get("HeldItem"), DRINK))
    text(g, g.append("В руках  ·  ", drink_label(g, g.get("HeldDrink"))), 247, 367, 0.9, BLUE)
    service_button(g, RETURN_BUTTON, "4", "Вернуть банку", tint=BLUE)


def draw_pc_recovery(g):
    desk = g.get("ServicePc")
    frozen = g.eq(g.arr("RequestVariant", desk), GAME_FROZEN)
    stopped = g.eq(g.arr("RecoveryStage", desk), 1)
    booting = g.gt(g.arr("RestartUntil", desk), 0)
    fault = words(g, frozen, "Игра не отвечает", "Лаунчер не отвечает")
    ready = words(g, frozen, "Игра закрыта", "Лаунчер запущен")
    status = words(g, booting, "Запускаю игру…", words(g, stopped, ready, fault))
    service_shell(g, g.append("ПК ", g.string(g.add(desk, 1))), status,
                  color_when(g, g.either(stopped, booting), TEAL, AMBER))
    for index, (label, box) in enumerate(zip(("Завершить игру", "Перезапустить лаунчер", "Запустить игру"), PC_BUTTONS), 1):
        service_button(g, box, str(index), label, enabled=g.negate(booting))
    hint = ""
    for index, label in ((END_GAME, "Сначала заверши зависшую игру."),
                         (RESTART_LAUNCHER, "Сначала перезапусти лаунчер."),
                         (START_GAME, "Теперь запусти игру.")):
        hint = words(g, g.eq(g.get("ServiceHint"), index), label, hint)
    text(g, hint, 272, 432, 0.97, PINK)


def draw_service_panel(g):
    g.guard(g.gt(g.get("ServicePanel"), NO_SERVICE_PANEL))
    other = g.branch(g.eq(g.get("ServicePanel"), DRINK_PANEL))
    g.call("DrawFridgePanel")
    g.resume(other)
    g.call("DrawPcRecovery")


SERVICE_GRAPHS = (
    ("ResetService", reset_service, ()), ("CloseServicePanel", close_service_panel, ()),
    ("OpenFridgePanel", open_fridge, ()), ("OpenPcPanel", open_pc, I),
    ("ChooseDrink", choose_drink, (("Choice", "int"),)),
    ("ChoosePcAction", choose_pc_action, I + (("Choice", "int"),)),
    ("FinishPcRecovery", finish_pc_recovery, I),
    ("UseMicrowave", use_microwave, ()), ("AdvanceMicrowave", advance_microwave, ()),
    ("ProcessServiceChoice", process_choice, (("Choice", "int"),)),
    ("ServicePanelInput", service_input, ()),
    ("DrawServicePanel", draw_service_panel, ()), ("DrawFridgePanel", draw_fridge, ()),
    ("DrawPcRecovery", draw_pc_recovery, ()),
)
