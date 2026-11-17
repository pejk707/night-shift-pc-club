"""Connect the imported CommonUI menus to Night Shift and draw settings and shift results."""

from blueprint_graph import ARRAY, SYSTEM
from club_rules import NO_SERVICE_PANEL, max_int, player_pawn
from club_screen import (
    AMBER, BLUE, CARD, INSET, MUTED, PINK, RAIL, TEAL, WHITE, as_real, color_when, keycap,
    modal_surface, progress_bar, rect, rgb, surface, text, words,
)

MAIN, PAUSE, SETTINGS, CONTROLS, CONFIRM, RESULTS = range(1, 7)
PLAY, RESUME, OPTIONS, HELP, QUIT, GO_MAIN, BACK, CONFIRM_MAIN, NEXT_SHIFT = range(1, 10)
WINDOW, QUALITY, VSYNC, FPS = range(10, 14)
MENU_INT_DEFAULTS = dict(ClubMenu=0, MenuReturn=MAIN)
ACTOR = "/Script/Engine.Actor"
UMG = "/Script/UMG."
KIT_COMMANDS = {
    PLAY: "ClubMenu.Play", RESUME: "ClubMenu.Resume", OPTIONS: "ClubMenu.Options",
    HELP: "ClubMenu.Help", QUIT: "ClubMenu.Quit", GO_MAIN: "ClubMenu.Main",
}
KIT_WIDGETS = ((MAIN, "UI_MainMenu"), (PAUSE, "UI_Pause"))
SETTINGS_ROWS = ((WINDOW, "Режим окна"), (QUALITY, "Качество графики"),
                 (VSYNC, "Вертикальная синхронизация"), (FPS, "Ограничение FPS"))
SETTINGS_BOXES = tuple((716, 215 + index * 61, 205, 42) for index in range(len(SETTINGS_ROWS)))
BACK_BOX = (254, 490, 150, 40)
CONFIRM_BOX = (630, 365, 185, 49)
CONFIRM_BACK_BOX = (375, 365, 180, 49)
RESULT_NEXT_BOX = (343, 474, 280, 52)
RESULT_MAIN_BOX = (656, 474, 230, 52)
BACKDROP = rgb("08111C", 0.68)


def controller(g):
    return g.invoke("HUD.GetOwningPlayerController", result="ReturnValue")


def is_valid(g, value):
    return g.invoke(SYSTEM + "IsValid", result="ReturnValue", Object=value)


def menu_tags(g, hud=None):
    return g.get("Tags", class_path=ACTOR, target=hud)


def remove_kit_widget(g):
    widget = g.get("ClubMenuWidget")
    g.guard(is_valid(g, widget))
    g.invoke(UMG + "Widget.RemoveFromParent", target=widget)
    g.set("ClubMenuWidget", "None")


def show_club_menu(g):
    screen = g.get("Screen")
    g.call("RemoveKitMenuWidget")
    g.set("ClubMenu", screen)
    g.call("SetRepairCursor", Shown=True)
    for mode, name in KIT_WIDGETS:
        next_screen = g.branch(g.eq(screen, mode))
        path = f"/Game/UI/{name}.{name}_C"
        widget = g.invoke(UMG + "WidgetBlueprintLibrary.Create", result="ReturnValue",
                          WidgetType=path, OwningPlayer=controller(g))
        g.guard(is_valid(g, widget))
        g.set("ClubMenuWidget", widget)
        g.invoke(UMG + "UserWidget.AddToViewport", target=widget, ZOrder=10)
        g.resume(next_screen)


def show_main_menu(g):
    g.call("ShowClubMenu", Screen=MAIN)


def show_pause_menu(g):
    g.call("ShowClubMenu", Screen=PAUSE)
    g.guard(g.get("Scene3D"))
    component = g.invoke("Actor.GetComponentByClass", result="ReturnValue", target=player_pawn(g),
                         ComponentClass="/Script/Engine.CharacterMovementComponent")
    g.guard(is_valid(g, component))
    g.invoke("MovementComponent.StopMovementImmediately", target=component)


def show_shift_results(g):
    g.call("ShowClubMenu", Screen=RESULTS)


def close_club_menu(g):
    g.guard(g.gt(g.get("ClubMenu"), 0))
    g.call("RemoveKitMenuWidget")
    g.set("ClubMenu", 0)
    restore_cursor = g.either(g.get("RepairOpen"), g.gt(g.get("ServicePanel"), NO_SERVICE_PANEL))
    g.call("SetRepairCursor", Shown=restore_cursor)


def return_to_main(g):
    g.set("Phase", 4)
    g.call("ContinueGame")
    g.set("Phase", 0)
    g.call("ShowMainMenu")


def menu_action(g):
    choice = g.get("Choice")
    screen = g.get("ClubMenu")
    for action, function in ((PLAY, "ContinueGame"), (NEXT_SHIFT, "ContinueGame"),
                             (RESUME, "CloseClubMenu"), (CONFIRM_MAIN, "ReturnToMainMenu")):
        other = g.branch(g.eq(choice, action))
        g.call(function)
        g.resume(other)
    subpage = g.either(g.eq(choice, OPTIONS), g.eq(choice, HELP))
    other = g.branch(subpage)
    g.set("MenuReturn", screen)
    g.call("ShowClubMenu", Screen=g.choose(g.eq(choice, OPTIONS), SETTINGS, CONTROLS))
    g.resume(other)
    other = g.branch(g.eq(choice, GO_MAIN))
    confirmed = g.branch(g.eq(screen, PAUSE))
    g.call("ShowClubMenu", Screen=CONFIRM)
    g.resume(confirmed)
    g.call("ReturnToMainMenu")
    g.resume(other)
    other = g.branch(g.eq(choice, BACK))
    next_page = g.choose(g.eq(screen, CONFIRM), PAUSE, g.get("MenuReturn"))
    g.call("ShowClubMenu", Screen=next_page)
    g.resume(other)
    other = g.branch(g.eq(choice, QUIT))
    g.invoke(SYSTEM + "QuitGame", SpecificPlayer=controller(g), QuitPreference="Quit")
    g.resume(other)
    g.guard(g.eq(screen, SETTINGS))
    g.call("ChangeClubSetting", Setting=choice)


def input_hit(g, bounds):
    x, y, width, height = bounds
    dx = g.math("Abs", A=g.sub(g.get("WireMouseX"), x, True))
    dy = g.math("Abs", A=g.sub(g.get("WireMouseY"), y, True))
    return g.both(g.lt(dx, width / 2, True), g.lt(dy, height / 2, True))


def input_action(g, action, bounds, keyboard=None):
    clicked = g.both(g.key("LeftMouseButton", just_pressed=True), input_hit(g, bounds))
    requested = g.either(clicked, g.key(keyboard, just_pressed=True)) if keyboard else clicked
    other = g.branch(requested)
    g.call("ClubMenuAction", Choice=action)
    g.resume(other)


def menu_input(g):
    for action, tag in KIT_COMMANDS.items():
        queued = g.invoke("Actor.ActorHasTag", result="ReturnValue", Tag=tag)
        other = g.branch(queued)
        g.invoke(ARRAY + "Array_RemoveItem", TargetArray=menu_tags(g), Item=tag)
        g.call("ClubMenuAction", Choice=action)
        g.resume(other)
    g.call("ReadPanelPointer")
    screen = g.get("ClubMenu")
    enter = g.key("Enter", just_pressed=True)
    back = g.either(g.key("Escape", just_pressed=True), g.key("P", just_pressed=True))
    other = g.branch(g.eq(screen, MAIN))
    g.guard(enter)
    g.call("ClubMenuAction", Choice=PLAY)
    g.resume(other)
    other = g.branch(g.eq(screen, PAUSE))
    g.guard(g.either(back, enter))
    g.call("ClubMenuAction", Choice=RESUME)
    g.resume(other)
    other = g.branch(g.eq(screen, RESULTS))
    input_action(g, NEXT_SHIFT, RESULT_NEXT_BOX, "Enter")
    input_action(g, GO_MAIN, RESULT_MAIN_BOX, "Escape")
    g.resume(other)
    other = g.branch(back)
    g.call("ClubMenuAction", Choice=BACK)
    g.resume(other)
    other = g.branch(g.eq(screen, CONFIRM))
    input_action(g, CONFIRM_MAIN, CONFIRM_BOX)
    input_action(g, BACK, CONFIRM_BACK_BOX)
    g.resume(other)
    input_action(g, BACK, BACK_BOX)
    g.guard(g.eq(screen, SETTINGS))
    for index, ((action, _), box) in enumerate(zip(SETTINGS_ROWS, SETTINGS_BOXES)):
        input_action(g, action, box, ("One", "Two", "Three", "Four")[index])


def settings(g):
    return g.invoke("GameUserSettings.GetGameUserSettings", result="ReturnValue")


def windowed(g, target):
    mode = g.invoke("GameUserSettings.GetFullscreenMode", target=target, result="ReturnValue")
    return g.eq(g.math("Conv_ByteToInt", InByte=mode), 2)


def change_setting(g):
    option = g.get("Setting")
    target = settings(g)
    other = g.branch(g.eq(option, WINDOW))
    fullscreen = g.branch(windowed(g, target))
    g.invoke("GameUserSettings.SetFullscreenMode", target=target, InFullscreenMode="WindowedFullscreen")
    g.invoke("GameUserSettings.ApplySettings", target=target, bCheckForCommandLineOverrides=False)
    g.resume(fullscreen)
    g.invoke("GameUserSettings.SetFullscreenMode", target=target, InFullscreenMode="Windowed")
    g.invoke("GameUserSettings.ApplySettings", target=target, bCheckForCommandLineOverrides=False)
    g.resume(other)
    other = g.branch(g.eq(option, QUALITY))
    current = g.invoke("GameUserSettings.GetOverallScalabilityLevel", target=target, result="ReturnValue")
    value = g.mod(max_int(g, 0, g.add(current, 1)), 4)
    g.invoke("GameUserSettings.SetOverallScalabilityLevel", target=target, Value=value)
    g.call("SaveClubSettings")
    g.resume(other)
    other = g.branch(g.eq(option, VSYNC))
    current = g.invoke("GameUserSettings.IsVSyncEnabled", target=target, result="ReturnValue")
    g.invoke("GameUserSettings.SetVSyncEnabled", target=target, bEnable=g.negate(current))
    g.call("SaveClubSettings")
    g.resume(other)
    g.guard(g.eq(option, FPS))
    current = g.invoke("GameUserSettings.GetFrameRateLimit", target=target, result="ReturnValue")
    value = 30.0
    for limit, next_limit in ((30, 60.0), (60, 120.0), (120, 0.0)):
        rounded = g.math("FTrunc", A=current)
        value = g.choose(g.eq(rounded, limit), next_limit, value, "Float")
    g.invoke("GameUserSettings.SetFrameRateLimit", target=target, NewLimit=value)
    g.call("SaveClubSettings")


def save_settings(g):
    target = settings(g)
    g.invoke("GameUserSettings.ApplyNonResolutionSettings", target=target)
    g.invoke("GameUserSettings.SaveSettings", target=target)


def button(g, bounds, label, *, accent=TEAL, primary_fill=None):
    x, y, width, height = bounds
    hover = input_hit(g, bounds)
    border = color_when(g, hover, accent, accent if primary_fill is not None else RAIL)
    fill = primary_fill if primary_fill is not None else INSET
    surface(g, x - width / 2, y - height / 2, width, height, stroke=border, face=fill)
    text(g, label, x - width / 2 + 17, y - 10, 1.12, WHITE)


def draw_settings(g):
    modal_surface(g, 137, 108, 726, 423, BLUE)
    text(g, "Настройки", 179, 129, 2.05)
    text(g, "Экран и производительность", 179, 165, 1.05, MUTED)
    target = settings(g)
    window = words(g, windowed(g, target), "В окне", "Без рамки")
    quality = g.invoke("GameUserSettings.GetOverallScalabilityLevel", target=target, result="ReturnValue")
    quality_label = "Свои настройки"
    for index, label in enumerate(("Низкое", "Среднее", "Высокое", "Эпическое", "Кино")):
        quality_label = words(g, g.eq(quality, index), label, quality_label)
    sync = g.invoke("GameUserSettings.IsVSyncEnabled", target=target, result="ReturnValue")
    vsync = words(g, sync, "Включена", "Выключена")
    limit = g.math("FTrunc", A=g.invoke("GameUserSettings.GetFrameRateLimit", target=target, result="ReturnValue"))
    fps = words(g, g.eq(limit, 0), "Без ограничения", g.append(g.string(limit), " FPS"))
    for index, ((_, label), value, box) in enumerate(zip(SETTINGS_ROWS, (window, quality_label, vsync, fps), SETTINGS_BOXES), 1):
        _, y, _, _ = box
        keycap(g, str(index), 179, y - 10)
        text(g, label, 216, y - 10, 1.16)
        button(g, box, value, accent=BLUE)
        text(g, "›", 800, y - 13, 1.2, BLUE)
        rect(g, 179, y + 29, 642, 1, RAIL)
    button(g, BACK_BOX, "Назад", accent=BLUE)
    text(g, "Изменения сохраняются автоматически", 520, 482, 0.97, MUTED)


def draw_controls(g):
    modal_surface(g, 205, 108, 590, 423, BLUE)
    text(g, "Управление", 245, 128, 2.05)
    for key, label, width, y in (
        ("WASD", "Ходить по залу", 49, 189), ("E", "Действие рядом с объектом", 27, 230),
        ("F", "Успокоить гостя в тильте", 27, 271), ("Q", "Отмена или убрать предмет", 27, 312),
        ("U", "Открыть улучшения клуба", 27, 353), ("Esc", "Поставить игру на паузу", 35, 394),
    ):
        keycap(g, key, 244, y, width)
        text(g, label, 311, y, 1.12)
    button(g, BACK_BOX, "Назад", accent=BLUE)


def draw_confirm(g):
    modal_surface(g, 243, 206, 514, 208, AMBER)
    text(g, "Вернуться в главное меню?", 277, 233, 1.74)
    text(g, "Текущая игра будет сброшена.", 278, 282, 1.12, MUTED)
    button(g, CONFIRM_BACK_BOX, "Отмена", accent=AMBER)
    button(g, CONFIRM_BOX, "В главное меню", accent=AMBER)


def draw_results(g):
    phase = g.get("Phase")
    victory = g.negate(g.eq(phase, 3))
    complete = g.eq(phase, 4)
    accent = color_when(g, victory, TEAL, PINK)
    modal_surface(g, 152, 96, 696, 426, accent)
    text(g, g.append("Смена ", g.string(g.get("ShiftNo")), " из 3"), 186, 122, 1.05, MUTED)
    title = words(g, complete, "Три смены пройдены",
                  words(g, victory, "План выполнен", "Смена провалена"))
    text(g, title, 184, 149, 2.45)
    cash, goal = g.get("Cash"), g.get("Goal")
    shortage = words(g, g.eq(g.get("Rating"), 0), "Рейтинг клуба упал до нуля.",
                     g.append("До плана не хватило ", g.string(max_int(g, 0, g.sub(goal, cash))), "."))
    reason = words(g, victory,
                   words(g, complete, "Клуб успешно отработал все три ночи.", "Следующая смена открыта."), shortage)
    text(g, reason, 186, 199, 1.13, MUTED)
    text(g, "Выручка / план", 187, 252, 1.02, MUTED)
    text(g, g.append(g.string(cash), " / ", g.string(goal)), 185, 277, 1.80, accent)
    progress_bar(g, 187, 313, 625, g.div(as_real(g, cash), as_real(g, goal), True), accent, 5)
    for label, value, x in (
        ("Рейтинг", g.append(g.string(g.get("Rating")), " / 5"), 187),
        ("Обслужено", g.string(g.get("Served")), 399),
        ("Ушли в ярости", g.string(g.get("Lost")), 610),
    ):
        surface(g, x, 338, 201, 81, face=INSET)
        text(g, label, x + 14, 350, 1.02, MUTED)
        text(g, value, x + 14, 374, 1.64)
    restart = words(g, complete, "Начать заново", words(g, victory, "Следующая смена", "Повторить смену"))
    fill = color_when(g, victory, rgb("154B47"), rgb("542536"))
    button(g, RESULT_NEXT_BOX, restart, accent=accent, primary_fill=fill)
    button(g, RESULT_MAIN_BOX, "Главное меню", accent=accent)


def draw_menu(g):
    screen = g.get("ClubMenu")
    for mode, writer in ((SETTINGS, "DrawClubSettings"), (CONTROLS, "DrawClubControls"),
                         (CONFIRM, "DrawClubConfirm"), (RESULTS, "DrawClubResults")):
        other = g.branch(g.eq(screen, mode))
        g.call(writer)
        g.resume(other)
    # Main and pause are actual CommonUI widgets from the installed menu kit.
    rect(g, 0, 0, 1000, 620, BACKDROP)


MENU_GRAPHS = (
    ("ShowClubMenu", show_club_menu, (("Screen", "int"),)),
    ("RemoveKitMenuWidget", remove_kit_widget, ()),
    ("ShowMainMenu", show_main_menu, ()), ("ShowPauseMenu", show_pause_menu, ()),
    ("ShowShiftResults", show_shift_results, ()), ("CloseClubMenu", close_club_menu, ()),
    ("ReturnToMainMenu", return_to_main, ()), ("ClubMenuAction", menu_action, (("Choice", "int"),)),
    ("ClubMenuInput", menu_input, ()), ("ChangeClubSetting", change_setting, (("Setting", "int"),)),
    ("SaveClubSettings", save_settings, ()),
    ("DrawClubMenu", draw_menu, ()), ("DrawClubSettings", draw_settings, ()),
    ("DrawClubControls", draw_controls, ()), ("DrawClubConfirm", draw_confirm, ()),
    ("DrawClubResults", draw_results, ()),
)
