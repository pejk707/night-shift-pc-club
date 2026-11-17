"""Build the Blueprint HUD and top-down club floor plan."""

from club_rules import (
    BENCH, BROKEN, COLD, CRASH, DESKS, DRINK, DRINK_NAMES, DURATION, ENERGY, FREE, FRIDGE, HEATING,
    HOT, KITCHEN, LINE_SIZE, MAX_UPGRADE_LEVEL, MOUSE, NERVOUS, NONE, NO_SLICE, PIZZA, PLAYING,
    RECEPTION, SERVER, SLICE, STOCK, SUPPLIES_NIGHT, UPGRADES, ceil_div, max_int, min_int,
    upgrade_effect, value_at_level, wallet,
)


def rgb(hexadecimal, alpha=1):
    def linear(channel):
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(int(hexadecimal[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return f"(R={r:.6f},G={g:.6f},B={b:.6f},A={alpha:.6f})"


BG = rgb("0B1019")
FLOOR = rgb("172439")
RAIL = rgb("354A60")
CARD = rgb("142131")
INSET = rgb("0C1724")
MUTED = rgb("BBC9DA")
WHITE = rgb("F5F8FD")
BLUE = rgb("7DD8FF")
TEAL = rgb("62F2CF")
PINK = rgb("FF8199")
AMBER = rgb("FFD27E")
VIOLET = rgb("CCB7FF")
OVERLAY = rgb("080E17", 0.77)
HUD_FACE = rgb("101C2B", 0.97)
SHADOW = rgb("030810", 0.55)
FONT = "/Engine/EngineFonts/Roboto.Roboto"


def as_real(g, value):
    return g.math("Conv_IntToDouble", InInt=value)


def scale(g, value):
    return g.mul(value, g.get("UiScale"), True)


def rect(g, x, y, w, h, color):
    g.invoke("HUD.DrawRect", RectColor=color, ScreenX=g.add(g.get("OriginX"), scale(g, x), True),
             ScreenY=g.add(g.get("OriginY"), scale(g, y), True), ScreenW=scale(g, w), ScreenH=scale(g, h))


def text(g, value, x, y, size=1.0, color=WHITE):
    g.invoke("HUD.DrawText", Text=value, TextColor=color, ScreenX=g.add(g.get("OriginX"), scale(g, x), True),
             ScreenY=g.add(g.get("OriginY"), scale(g, y), True), Font=FONT,
             Scale=scale(g, size), bScalePosition=False)


def text_right(g, value, right, y, size=1.0, color=WHITE):
    width = g.invoke("HUD.GetTextSize", result="OutWidth", Text=value, Font=FONT, Scale=size)
    text(g, value, g.sub(right, width, True), y, size, color)


def offset(g, coord, by):
    if isinstance(coord, (int, float)):
        return coord + by
    return g.add(coord, by, True)


def color_when(g, condition, yes, no):
    return g.choose(condition, yes, no, "Color")


def words(g, condition, yes, no):
    return g.choose(condition, yes, no, "String")


def drink_label(g, variant):
    label = DRINK_NAMES[0]
    for index, name in enumerate(DRINK_NAMES[1:], 1):
        label = words(g, g.eq(variant, index), name, label)
    return label


def cargo_label(g):
    item = g.get("HeldItem")
    cargo = words(g, g.eq(item, MOUSE), "Мышь", words(g, g.eq(item, SLICE), "Пицца", "Пусто"))
    return words(g, g.eq(item, DRINK), drink_label(g, g.get("HeldDrink")), cargo)


def request_seconds(g, desk):
    units_per_second = g.mul(max_int(g, g.arr("RequestRate", desk), 1), 10)
    return ceil_div(g, g.arr("RequestRemaining", desk), units_per_second)


def microwave_label(g, idle=""):
    state = g.get("MicrowaveState")
    seconds = g.string(ceil_div(g, max_int(g, 0, g.sub(g.get("MicrowaveAt"), g.get("Step"))), 10))
    ready = g.append("Пицца готова · ", seconds, " с")
    heating = g.append("Пицца греется · ", seconds, " с")
    cold = words(g, g.eq(state, COLD), "Пицца остыла", idle)
    return words(g, g.eq(state, HOT), ready, words(g, g.eq(state, HEATING), heating, cold))


def panel(g, x, y, width, height, selected=False):
    rect(g, x, y, width, height, color_when(g, selected, TEAL, RAIL))
    rect(g, offset(g, x, 2.0), offset(g, y, 2.0), width - 4, height - 4, CARD)


def surface(g, x, y, width, height, *, stroke=RAIL, face=HUD_FACE):
    rect(g, offset(g, x, 2.0), offset(g, y, 4.0), width, height, SHADOW)
    rect(g, x, y, width, height, stroke)
    rect(g, offset(g, x, 1.0), offset(g, y, 1.0), width - 2, height - 2, face)


def keycap(g, key, x, y, width=22, *, tint=BLUE, height=20):
    rect(g, x, y, width, height, RAIL)
    rect(g, offset(g, x, 1.0), offset(g, y, 1.0), width - 2, height - 3, INSET)
    text(g, key, offset(g, x, 5.0), offset(g, y, 2.0), 0.91, tint)


def progress_bar(g, x, y, width, ratio, tint, height=3):
    rect(g, x, y, width, height, RAIL)
    rect(g, x, y, g.mul(g.clamp(ratio, 0.0, 1.0), width, True), height, tint)


def modal_surface(g, x, y, width, height, accent):
    rect(g, 0, 0, 1000, 620, OVERLAY)
    surface(g, x, y, width, height, face=CARD)
    rect(g, offset(g, x, 1.0), offset(g, y, 1.0), width - 2, 3, accent)


def clock(g):
    total_minutes = g.add(22 * 60, g.div(g.mul(g.get("Step"), 480), DURATION))
    hours, minutes = g.mod(g.div(total_minutes, 60), 24), g.mod(total_minutes, 60)
    h = g.append(words(g, g.lt(hours, 10), "0", ""), g.string(hours))
    m = g.append(words(g, g.lt(minutes, 10), "0", ""), g.string(minutes))
    return g.append(h, ":", m)


def draw_header(g):
    surface(g, 18, 10, 964, 76)
    rect(g, 34, 22, 3, 35, TEAL)
    text(g, "Ночная смена", 47, 20, 1.95)
    text(g, g.append("Смена ", g.string(g.get("ShiftNo")), " из 3"), 48, 48, 0.99, MUTED)
    progress_bar(g, 48, 69, 183, g.div(as_real(g, g.get("Step")), DURATION, True), TEAL)
    cash, goal = g.get("Cash"), g.get("Goal")
    for divider in (254, 397, 627, 793):
        rect(g, divider, 27, 1, 43, RAIL)
    for title, value, x, tint in (
        ("Время", clock(g), 273, WHITE),
        ("Выручка / план", g.append(g.string(cash), " / ", g.string(goal)), 416, TEAL),
        ("Рейтинг", g.append(g.string(g.get("Rating")), " / 5"), 648, AMBER),
        ("Ушли в ярости", g.string(g.get("Lost")), 815, color_when(g, g.gt(g.get("Lost"), 0), PINK, WHITE)),
    ):
        text(g, title, x, 23, 1.0, MUTED)
        text(g, value, x, 39, 1.83, tint)
    progress_bar(g, 417, 70, 166, g.div(as_real(g, cash), as_real(g, goal), True), TEAL)


def board(g):
    rect(g, 0, 0, 1000, 620, BG)
    rect(g, 28, 101, 944, 451, RAIL)
    rect(g, 30, 103, 940, 447, FLOOR)
    rect(g, 30, 103, 940, 4, BLUE)
    rect(g, 216, 149, 1, 369, RAIL)
    rect(g, 838, 149, 1, 369, RAIL)
    rect(g, 240, 336, 582, 2, RAIL)
    draw_header(g)
    text(g, "ОЧЕРЕДЬ", 46, 157, 0.9, MUTED)
    text(g, "РЯД А", 244, 160, 0.9, MUTED)
    text(g, "РЯД Б", 244, 354, 0.9, MUTED)
    text(g, "СЛУЖЕБНАЯ ЗОНА", 850, 157, 0.74, MUTED)


def desk_card(g):
    index, x, y = g.get("Desk"), g.get("Left"), g.get("Top")
    status = g.arr("DeskState", index)
    enabled = g.lt(index, g.get("Places"))
    is_free, is_playing = g.eq(status, FREE), g.eq(status, PLAYING)
    is_broken, is_crash, is_drink = g.eq(status, BROKEN), g.eq(status, CRASH), g.eq(status, ENERGY)
    request = g.both(g.gt(status, PLAYING), g.negate(is_broken))
    patience = g.arr("Patience", index)
    tilting = g.both(request, g.lt(patience, 30))
    label = words(g, is_drink, drink_label(g, g.arr("RequestVariant", index)), "Пицца")
    playing = words(g, g.eq(g.get("ServerDown"), 1), "Нет сети", "Играет")
    for cond, title in ((is_broken, "Мышь сломана"), (is_crash, "Игра вылетела"), (is_playing, playing), (is_free, "Свободен"), (g.negate(enabled), "Пока недоступен")):
        label = words(g, cond, title, label)
    tint = color_when(g, g.either(tilting, is_broken), PINK,
                      color_when(g, request, AMBER, color_when(g, is_playing, TEAL, MUTED)))
    panel(g, x, y, 137, 113, g.both(enabled, g.eq(g.get("Focus"), index)))
    rect(g, offset(g, x, 11), offset(g, y, 11), 34, 22, INSET)
    rect(g, offset(g, x, 14), offset(g, y, 14), 28, 15, tint)
    rect(g, offset(g, x, 25), offset(g, y, 32), 6, 5, INSET)
    text(g, g.append("ПК ", g.string(g.add(index, 1))), offset(g, x, 53), offset(g, y, 14), 1.04)
    text(g, label, offset(g, x, 11), offset(g, y, 47), 0.85, tint)
    mood = words(g, g.eq(g.arr("Temper", index), 1), "нервный", "спокойный")
    mood = words(g, tilting, "ТИЛЬТ", mood)
    show_mood = g.both(enabled, g.both(g.negate(is_free), g.negate(is_broken)))
    opens = words(g, g.eq(index, 6), "Со 2-й смены", "С 3-й смены")
    detail = words(g, enabled, words(g, show_mood, mood, ""), opens)
    seconds = g.append(g.string(request_seconds(g, index)), " с")
    detail = words(g, g.both(enabled, request), g.append(mood, " · ", seconds), detail)
    text(g, detail, offset(g, x, 11), offset(g, y, 68), 0.79, MUTED)
    rect(g, offset(g, x, 11), offset(g, y, 96), 115, 4, RAIL)
    width = g.mul(as_real(g, g.choose(request, patience, 0)), 1.15, True)
    rect(g, offset(g, x, 11), offset(g, y, 96), width, 4, tint)


def station(g):
    index, x, y = g.get("Station"), g.get("Left"), g.get("Top")
    chosen = g.eq(g.get("Focus"), index)
    panel(g, x, y, 146, 65, chosen)
    text(g, g.get("Title"), offset(g, x, 10), offset(g, y, 11), 0.94)
    text(g, g.get("Status"), offset(g, x, 10), offset(g, y, 33), 0.85, g.get("Tint"))


def station_right(g):
    index, y = g.get("Station"), g.get("Top")
    panel(g, 848, y, 114, 81, g.eq(g.get("Focus"), index))
    text(g, g.get("Title"), 858, offset(g, y, 14), 0.93)
    text(g, g.get("Status"), 858, offset(g, y, 39), 0.75, g.get("Tint"))


def draw_queue(g):
    panel(g, 44, 189, 146, 142, g.eq(g.get("Focus"), RECEPTION))
    rect(g, 54, 260, 126, 1, RAIL)
    for slot in range(LINE_SIZE):
        y = 203 + slot * 69
        mood = g.arr("LineMood", slot)
        present = g.gt(mood, 0)
        nervous = g.eq(mood, NERVOUS)
        title = words(g, nervous, "Нервный", "Спокойный")
        label = words(g, present, title, "Очередь пуста" if slot == 0 else "")
        color = color_when(g, present, color_when(g, nervous, VIOLET, TEAL), MUTED)
        text(g, label, 54, y, 0.94, color)
        seconds = g.string(g.div(g.add(g.arr("LineWait", slot), 9), 10))
        action = words(g, g.gt(g.get("Guest"), 0), "Выбран", "E — позвать") if slot == 0 else "Ждёт"
        text(g, words(g, present, g.append(action, " · ", seconds, " с"), ""), 54, y + 25, 0.82, MUTED)


def floor_objects(g):
    for desk in range(8):
        g.call("DrawDesk", Desk=desk, Left=244.0 + 146.0 * (desk % 4), Top=187.0 + 190.0 * (desk // 4))
    g.call("DrawQueue")
    supplies_open = g.negate(g.lt(g.get("ShiftNo"), SUPPLIES_NIGHT))
    for index, top, title, status, tint in (
        (FRIDGE, 357.0, "Холодильник", "Энергетики", BLUE),
        (STOCK, 445.0, "Склад · мыши", words(g, supplies_open, "Запасные мыши", "Пока недоступно"),
         color_when(g, supplies_open, VIOLET, MUTED)),
    ):
        g.call("DrawStation", Station=index, Left=44.0, Top=top, Title=title, Status=status, Tint=tint)
    off = g.gt(g.get("ServerDown"), 0)
    g.call("DrawRight", Station=SERVER, Top=187.0, Title="Сервер", Status=words(g, off, "Оффлайн", "В сети"),
           Tint=color_when(g, off, PINK, TEAL))
    g.call("DrawRight", Station=KITCHEN, Top=400.0, Title="Снэк-бар",
           Status=words(g, supplies_open, "Пицца", "Пока недоступно"),
           Tint=color_when(g, supplies_open, AMBER, MUTED))
    text(g, microwave_label(g), 849, 489, 0.68, AMBER)
    unlock = words(g, supplies_open, "", "Со 2-й смены")
    text(g, unlock, 54, 514, 0.78, MUTED)
    text(g, unlock, 858, 464, 0.78, MUTED)


def draw_player(g):
    x, y = g.get("PlayerX"), g.get("PlayerY")
    rect(g, offset(g, x, -11), offset(g, y, -11), 22, 22, INSET)
    rect(g, offset(g, x, -8), offset(g, y, -8), 16, 16, TEAL)
    rect(g, offset(g, x, -4), offset(g, y, -4), 8, 8, WHITE)
    text(g, g.append("Предмет  /  ", cargo_label(g)), 29, 572, 1.09, TEAL)
    text(g, "WASD  идти     E  действие / удерживать     F  успокоить     Q  отменить", 275, 574, 0.9, WHITE)
    text(g, "U  улучшения", 849, 574, 1.0, TEAL)
    limit = g.call("InteractDuration", result="Value")
    g.guard(g.gt(g.get("HoldTime"), 0.0, True))
    g.guard(g.gt(limit, 0.0, True))
    rect(g, offset(g, x, -23), offset(g, y, 16), 46, 5, INSET)
    progress = g.clamp(g.div(g.get("HoldTime"), limit, True), 0.0, 1.0)
    rect(g, offset(g, x, -23), offset(g, y, 16), g.mul(progress, 46.0, True), 5, AMBER)


def draw_shop(g):
    modal_surface(g, 137, 112, 726, 431, TEAL)
    text(g, "Улучшения клуба", 163, 132, 1.95)
    balance = wallet(g)
    text(g, g.append("В кассе ", g.string(balance)), 629, 143, 1.06, TEAL)
    text(g, "Нажми 1–5, чтобы купить уровень", 164, 171, 1.02, MUTED)
    rect(g, 164, 194, 672, 1, RAIL)
    for index, upgrade in enumerate(UPGRADES, start=1):
        y = 204 + (index - 1) * 57
        level = g.get(upgrade.member)
        maxed = g.eq(level, MAX_UPGRADE_LEVEL)
        price = value_at_level(g, level, upgrade.prices)
        affordable = g.negate(g.lt(balance, price))
        current_effect = value_at_level(g, level, upgrade.values)
        next_effect = value_at_level(g, g.add(level, 1), upgrade.values)
        change = words(g, maxed, "", g.append(" → ", g.string(next_effect), upgrade.unit))
        cost = g.append("Цена ", g.string(price))
        shortage = g.append(" · не хватает ", g.string(g.sub(price, balance)))
        status = words(g, maxed, "Максимум", g.append(cost, words(g, affordable, "", shortage)))
        keycap(g, str(index), 165, y + 2)
        text(g, upgrade.title, 198, y, 1.16)
        text(g, g.append(upgrade.effect, " · ", g.string(current_effect), upgrade.unit, change),
             198, y + 24, 0.93, MUTED)
        text(g, g.append("Уровень ", g.string(level), f" / {MAX_UPGRADE_LEVEL}"), 629, y, 0.98)
        text(g, status, 629, y + 24, 0.88,
             color_when(g, maxed, TEAL, color_when(g, affordable, AMBER, MUTED)))
        rect(g, 164, y + 47, 672, 1, RAIL)
    keycap(g, "U", 164, 504, tint=TEAL)
    text(g, "Вернуться в клуб", 199, 503, 1.11, TEAL)
    text(g, "Смена на паузе", 629, 503, 0.9, MUTED)


def draw_scene_pc_status(g):
    desk = g.get("Desk")
    anchor = g.arr("PcStatusAnchors", desk)
    g.guard(g.gt(g.math("VSizeSquared", A=anchor), 1.0, True))
    projected = g.invoke("HUD.Project", result="ReturnValue", Location=anchor)
    px, py, depth = g.invoke("KismetMathLibrary.BreakVector", result=("X", "Y", "Z"), InVec=projected)
    g.guard(g.gt(depth, 0.0, True))
    # HUD.Project already uses the same camera canvas as DrawText and DrawRect.
    center_x = g.div(g.sub(px, g.get("OriginX"), True), g.get("UiScale"), True)
    center_y = g.div(g.sub(py, g.get("OriginY"), True), g.get("UiScale"), True)
    left, top = offset(g, center_x, -38.0), offset(g, center_y, -18.0)

    state = g.arr("DeskState", desk)
    open_pc = g.lt(desk, g.get("Places"))
    offline = g.eq(g.get("ServerDown"), 1)
    restarting = g.gt(g.arr("RestartUntil", desk), 0)
    playing = words(g, offline, "Нет сети", "Играет")
    crash = words(g, restarting, "Запуск", "Вылет")
    label = "Пицца"
    for value, name in ((FREE, "Свободен"), (PLAYING, playing), (CRASH, crash),
                        (ENERGY, drink_label(g, g.arr("RequestVariant", desk))), (BROKEN, "Мышь")):
        label = words(g, g.eq(state, value), name, label)
    patience = g.arr("Patience", desk)
    pending = g.both(open_pc, g.both(g.gt(state, PLAYING), g.negate(g.eq(state, BROKEN))))
    urgent = g.both(pending, g.lt(patience, 30))
    danger = g.either(urgent, g.either(g.eq(state, BROKEN), g.both(offline, g.eq(state, PLAYING))))
    state_color = color_when(g, danger, PINK, color_when(g, pending, AMBER, TEAL))
    state_color = color_when(g, open_pc, state_color, MUTED)
    focus = g.both(open_pc, g.eq(g.get("Focus"), desk))
    surface(g, left, top, 76, 36, stroke=color_when(g, focus, TEAL, RAIL))
    rect(g, offset(g, left, 1.0), offset(g, top, 5.0), 2, 26, state_color)
    show_time = g.both(pending, g.negate(restarting))
    label_y = offset(g, top, g.choose(show_time, 3.0, 9.0, "Float"))
    tint = color_when(g, open_pc, WHITE, MUTED)
    text(g, words(g, open_pc, label, "Закрыт"), offset(g, left, 7.0), label_y, 0.96, tint)
    g.guard(show_time)
    seconds = request_seconds(g, desk)
    text_right(g, g.append(g.string(seconds), " с"), offset(g, left, 69.0), offset(g, top, 18.0), 0.95, state_color)
    progress_bar(g, offset(g, left, 7.0), offset(g, top, 27.0), 30,
                 g.div(as_real(g, patience), 100.0, True), state_color)


def draw_scene_queue_row(g):
    slot = g.get("Slot")
    mood = g.arr("LineMood", slot)
    g.guard(g.gt(mood, 0))
    waiting = g.arr("LineWait", slot)
    y = g.add(139.0, g.mul(as_real(g, slot), 33.0, True), True)
    selected = g.both(g.eq(slot, 0), g.gt(g.get("Guest"), 0))
    nervous = g.eq(mood, NERVOUS)
    title = words(g, nervous, "Нервный", "Спокойный")
    tint = color_when(g, g.lt(waiting, 81), PINK, color_when(g, nervous, VIOLET, TEAL))
    rect(g, 30, offset(g, y, 5.0), 4, 9, tint)
    text(g, words(g, selected, "Гость выбран", title), 40, y, 0.98)
    text_right(g, g.append(g.string(ceil_div(g, waiting, 10)), " с"), 155, y, 0.92, tint)
    base = g.choose(nervous, 240, 300)
    budget = g.add(base, g.mul(upgrade_effect(g, BENCH), 10))
    progress_bar(g, 40, offset(g, y, 20.0), 115, g.div(as_real(g, waiting), as_real(g, budget), True), tint, 2)


def draw_scene_queue(g):
    focus = g.eq(g.get("Focus"), RECEPTION)
    stroke = color_when(g, focus, TEAL, RAIL)
    empty = g.eq(g.arr("LineMood", 0), 0)
    one = g.eq(g.arr("LineMood", 1), 0)
    no_line = g.branch(empty)
    surface(g, 18, 105, 150, 63, stroke=stroke)
    text(g, "Очередь", 30, 113, 1.17)
    text(g, "Пусто", 30, 140, 1.02, MUTED)
    g.resume(no_line)
    full = g.branch(one)
    surface(g, 18, 105, 150, 68, stroke=stroke)
    text(g, "Очередь", 30, 113, 1.17)
    g.call("DrawSceneQueueRow", Slot=0)
    g.resume(full)
    surface(g, 18, 105, 150, 102, stroke=stroke)
    text(g, "Очередь", 30, 113, 1.17)
    for slot in range(LINE_SIZE):
        g.call("DrawSceneQueueRow", Slot=slot)


def draw_scene_action(g):
    focus = g.get("Focus")
    g.guard(g.gt(focus, -1))
    online_server = g.both(g.eq(focus, SERVER), g.eq(g.get("ServerDown"), 0))
    g.guard(g.negate(online_server))
    desk = min_int(g, max_int(g, 0, focus), DESKS - 1)
    pc = g.lt(focus, DESKS)
    item = g.get("HeldItem")
    empty = g.eq(item, NONE)
    state = g.arr("DeskState", desk)
    drink = g.arr("RequestVariant", desk)
    drink_name = drink_label(g, drink)
    has_drink = g.both(g.eq(item, DRINK), g.eq(g.get("HeldDrink"), drink))
    has_slice = g.eq(item, SLICE)
    has_mouse = g.eq(item, MOUSE)
    seating = g.gt(g.get("Guest"), 0)
    booting = g.gt(g.arr("RestartUntil", desk), 0)
    available = g.lt(desk, g.get("Places"))
    title = g.append("ПК ", g.string(g.add(desk, 1)))
    action = "Свободен"
    enabled = seating
    for kind, label, can_act in (
        (FREE, words(g, seating, "Посадить гостя", "Свободен"), seating),
        (PLAYING, words(g, g.eq(g.get("ServerDown"), 1), "Нет сети", "Играет"), False),
        (CRASH, words(g, booting, "Игра запускается", "Открыть диагностику"), g.negate(booting)),
        (ENERGY, words(g, has_drink, "Отдать энергетик", g.append("Нужен энергетик · ", drink_name)), has_drink),
        (PIZZA, words(g, has_slice, "Отдать пиццу", "Заказ · кусок пиццы"), has_slice),
        (BROKEN, words(g, has_mouse, "Удерживай, чтобы заменить мышь", "Нужна запасная мышь"), has_mouse),
    ):
        matches = g.eq(state, kind)
        action = words(g, matches, label, action)
        enabled = g.either(g.both(matches, can_act), g.both(g.negate(matches), enabled))
    action = words(g, available, action, "Пока недоступен")
    enabled = g.both(pc, g.both(enabled, available))

    fridge_ready = g.either(empty, g.eq(item, DRINK))
    waiting_guest = g.gt(g.arr("LineMood", 0), 0)
    supplies = g.negate(g.lt(g.get("ShiftNo"), SUPPLIES_NIGHT))
    offline = g.eq(g.get("ServerDown"), 1)
    microwave = g.get("MicrowaveState")
    hot = g.eq(microwave, HOT)
    heating = g.eq(microwave, HEATING)
    can_use_microwave = g.both(g.negate(heating), g.either(empty, g.negate(hot)))
    pizza = words(g, g.eq(microwave, NO_SLICE), "Поставить пиццу",
                  words(g, g.eq(microwave, COLD), "Снова разогреть",
                        words(g, hot, words(g, empty, "Забрать пиццу", "Освободи руки"), "Микроволновка греет")))
    for station, label, hint, can_act in (
        (RECEPTION, "Стойка", words(g, waiting_guest, "Позвать гостя", "Очередь пуста"), waiting_guest),
        (FRIDGE, "Холодильник", words(g, fridge_ready, "Выбрать энергетик", "Освободи руки"), fridge_ready),
        (STOCK, "Склад", words(g, supplies, words(g, empty, "Взять мышь", "Освободи руки"), "Со второй смены"),
         g.both(supplies, empty)),
        (SERVER, "Сервер", words(g, offline, "Открыть панель ремонта", "Сервер в сети"), offline),
        (KITCHEN, "Снэк-бар", words(g, supplies, pizza, "Со второй смены"), g.both(supplies, can_use_microwave)),
    ):
        matches = g.eq(focus, station)
        title = words(g, matches, label, title)
        action = words(g, matches, hint, action)
        enabled = g.either(enabled, g.both(matches, can_act))

    surface(g, 258, 547, 483, 46, stroke=color_when(g, enabled, TEAL, RAIL))
    text(g, title, 271, 551, 0.89, MUTED)
    x = g.choose(enabled, 302.0, 271.0, "Float")
    text(g, action, x, 568, 1.1)
    active = g.branch(enabled)
    keycap(g, "E", 270, 568, tint=TEAL, height=18)
    g.resume(active)
    limit = g.call("InteractDuration", result="Value")
    holding = g.both(g.gt(limit, 0.0, True), g.gt(g.get("HoldTime"), 0.0, True))
    g.guard(g.both(enabled, holding))
    progress_bar(g, 604, 574, 120, g.div(g.get("HoldTime"), limit, True), AMBER, 5)


def draw_scene_controls(g):
    surface(g, 18, 547, 224, 46)
    text(g, "В руках", 32, 551, 0.89, MUTED)
    text(g, cargo_label(g), 32, 568, 1.13)
    g.call("DrawSceneAction")
    surface(g, 757, 547, 225, 46)
    offline = g.eq(g.get("ServerDown"), 1)
    color = color_when(g, offline, PINK, TEAL)
    text(g, "Сервер", 771, 551, 0.89, MUTED)
    rect(g, 771, 574, 6, 6, color)
    text(g, words(g, offline, "Отключён", "В сети"), 783, 569, 1.06, color)
    rect(g, 865, 557, 1, 27, RAIL)
    keycap(g, "U", 874, 563, 20, tint=TEAL, height=19)
    text(g, "Улучшения", 900, 564, 1.0)
    for key, label, x, width in (
        ("WASD", "Движение", 18, 48),
        ("F", "Успокоить", 158, 21),
        ("Q", "Отмена", 270, 21),
    ):
        keycap(g, key, x, 600, width)
        text(g, label, x + width + 7, 602, 0.94, MUTED)
    text(g, microwave_label(g), 532, 601, 1.0, AMBER)


def draw_scene_frame(g):
    draw_header(g)
    g.call("DrawSceneQueue")
    for index in range(DESKS):
        g.call("DrawScenePcStatus", Desk=index)
    g.call("DrawSceneControls")
    g.call("DrawServicePanel")
    ordinary = g.branch(g.get("RepairOpen"))
    g.call("DrawRepair")
    g.resume(ordinary)
    g.guard(g.get("ShopOpen"))
    g.call("DrawShop")


def draw_frame(g):
    width, height = as_real(g, g.get("Width")), as_real(g, g.get("Height"))
    g.set("UiScale", g.math("FMin", A=g.div(width, 1000.0, True), B=g.div(height, 620.0, True)))
    g.set("OriginX", g.mul(g.sub(width, scale(g, 1000.0), True), 0.5, True))
    g.set("OriginY", g.mul(g.sub(height, scale(g, 620.0), True), 0.5, True))
    controller = g.invoke("HUD.GetOwningPlayerController", result="ReturnValue")
    viewport_x, viewport_y = g.invoke("PlayerController.GetViewportSize", target=controller, result=("SizeX", "SizeY"))
    # Canvas starts inside the camera's letterbox. The cursor uses the full viewport.
    for member, viewport, canvas, origin in (
        ("MouseOriginX", viewport_x, width, "OriginX"), ("MouseOriginY", viewport_y, height, "OriginY"),
    ):
        border = g.mul(g.sub(as_real(g, viewport), canvas, True), 0.5, True)
        g.set(member, g.add(g.get(origin), border, True))
    playing = g.branch(g.gt(g.get("ClubMenu"), 0))
    g.call("DrawClubMenu")
    g.resume(playing)
    g.guard(g.eq(g.get("Phase"), 1))
    flat_view = g.branch(g.get("Scene3D"))
    g.call("DrawSceneFrame")
    g.resume(flat_view)
    g.invoke("HUD.DrawRect", RectColor=BG, ScreenX=0, ScreenY=0, ScreenW=width, ScreenH=height)
    g.call("DrawBoard")
    g.call("DrawFloorObjects")
    g.call("DrawPlayer")
    g.call("DrawServicePanel")
    regular = g.branch(g.get("RepairOpen"))
    g.call("DrawRepair")
    g.resume(regular)
    g.guard(g.get("ShopOpen"))
    g.call("DrawShop")


XY = (("Left", "real"), ("Top", "real"))
LABEL = (("Title", "string"), ("Status", "string"), ("Tint", "color"))
SCREEN_GRAPHS = (
    ("DrawBoard", board, ()), ("DrawDesk", desk_card, (("Desk", "int"),) + XY),
    ("DrawStation", station, (("Station", "int"),) + XY + LABEL),
    ("DrawRight", station_right, (("Station", "int"), ("Top", "real")) + LABEL),
    ("DrawQueue", draw_queue, ()), ("DrawFloorObjects", floor_objects, ()), ("DrawPlayer", draw_player, ()),
    ("DrawShop", draw_shop, ()),
    ("DrawSceneFrame", draw_scene_frame, ()),
    ("DrawScenePcStatus", draw_scene_pc_status, (("Desk", "int"),)),
    ("DrawSceneQueue", draw_scene_queue, ()),
    ("DrawSceneQueueRow", draw_scene_queue_row, (("Slot", "int"),)),
    ("DrawSceneControls", draw_scene_controls, ()),
    ("DrawSceneAction", draw_scene_action, ()),
    ("DrawFrame", draw_frame, (("Width", "int"), ("Height", "int"))),
)
