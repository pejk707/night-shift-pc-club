"""Build the Blueprint HUD and top-down club floor plan."""

from club_rules import BROKEN, CRASH, DURATION, ENERGY, FOOD, FREE, PLAYING


def rgb(hexadecimal, alpha=1):
    r, g, b = (int(hexadecimal[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return f"(R={r:.6f},G={g:.6f},B={b:.6f},A={alpha:.6f})"


BG = rgb("071018")
FLOOR = rgb("121E2C")
RAIL = rgb("27374C")
CARD = rgb("162634")
INSET = rgb("0A131D")
MUTED = rgb("99AECB")
WHITE = rgb("E7F2FB")
BLUE = rgb("69DBFF")
TEAL = rgb("64F1C5")
PINK = rgb("FF658F")
AMBER = rgb("FFCE7A")
VIOLET = rgb("AE99FF")
OVERLAY = rgb("060C14", 0.92)


def as_real(g, value):
    return g.math("Conv_IntToDouble", InInt=value)


def scale(g, value):
    return g.mul(value, g.get("UiScale"), True)


def rect(g, x, y, w, h, color):
    g.invoke("HUD.DrawRect", RectColor=color, ScreenX=g.add(g.get("OriginX"), scale(g, x), True),
             ScreenY=g.add(g.get("OriginY"), scale(g, y), True), ScreenW=scale(g, w), ScreenH=scale(g, h))


def text(g, value, x, y, size=1.0, color=WHITE):
    g.invoke("HUD.DrawText", Text=value, TextColor=color, ScreenX=g.add(g.get("OriginX"), scale(g, x), True),
             ScreenY=g.add(g.get("OriginY"), scale(g, y), True), Scale=scale(g, size), bScalePosition=False)


def offset(g, coord, by):
    if isinstance(coord, (int, float)):
        return coord + by
    return g.add(coord, by, True)


def color_when(g, condition, yes, no):
    return g.choose(condition, yes, no, "Color")


def words(g, condition, yes, no):
    return g.choose(condition, yes, no, "String")


def panel(g, x, y, width, height, selected=False):
    rect(g, x, y, width, height, color_when(g, selected, TEAL, RAIL))
    rect(g, offset(g, x, 2.0), offset(g, y, 2.0), width - 4, height - 4, CARD)


def clock(g):
    total_minutes = g.add(22 * 60, g.div(g.mul(g.get("Step"), 480), DURATION))
    hours, minutes = g.mod(g.div(total_minutes, 60), 24), g.mod(total_minutes, 60)
    h = g.append(words(g, g.lt(hours, 10), "0", ""), g.string(hours))
    m = g.append(words(g, g.lt(minutes, 10), "0", ""), g.string(minutes))
    return g.append(h, ":", m)


def board(g):
    rect(g, 0, 0, 1000, 620, BG)
    rect(g, 28, 101, 944, 451, RAIL)
    rect(g, 30, 103, 940, 447, FLOOR)
    rect(g, 30, 103, 940, 4, BLUE)
    rect(g, 216, 149, 1, 369, RAIL)
    rect(g, 838, 149, 1, 369, RAIL)
    rect(g, 240, 336, 582, 2, RAIL)
    text(g, "НОЧНАЯ СМЕНА", 29, 22, 2.0)
    text(g, "КОМПЬЮТЕРНЫЙ КЛУБ", 32, 55, 0.82, MUTED)
    for title, value, x, tint in (
        ("СМЕНА", g.append(g.string(g.get("ShiftNo")), " / 3"), 288, WHITE),
        ("ЧАСЫ", clock(g), 405, BLUE),
        ("ВЫРУЧКА / ПЛАН", g.append(g.string(g.get("Cash")), " / ", g.string(g.get("Goal"))), 522, TEAL),
        ("РЕЙТИНГ", g.append(g.string(g.get("Rating")), " / 5"), 718, AMBER),
        ("УШЛО В ЯРОСТИ", g.string(g.get("Lost")), 838, PINK),
    ):
        text(g, title, x, 25, 0.85, MUTED)
        text(g, value, x, 46, 1.5, tint)
    rect(g, 28, 84, 944, 3, RAIL)
    rect(g, 28, 84, g.div(g.mul(as_real(g, g.get("Step")), 944.0, True), DURATION, True), 3, TEAL)
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
    label = words(g, is_drink, "Энергетик", "Перекус")
    for cond, title in ((is_broken, "Мышь сломана"), (is_crash, "Игра вылетела"), (is_playing, "Играет"), (is_free, "Свободен"), (g.negate(enabled), "Закрыт")):
        label = words(g, cond, title, label)
    tint = color_when(g, g.either(tilting, is_broken), PINK,
                      color_when(g, request, AMBER, color_when(g, is_playing, TEAL, MUTED)))
    panel(g, x, y, 137, 113, g.eq(g.get("Focus"), index))
    rect(g, offset(g, x, 11), offset(g, y, 11), 34, 22, INSET)
    rect(g, offset(g, x, 14), offset(g, y, 14), 28, 15, tint)
    rect(g, offset(g, x, 25), offset(g, y, 32), 6, 5, INSET)
    text(g, g.append("ПК ", g.string(g.add(index, 1))), offset(g, x, 53), offset(g, y, 14), 1.04)
    text(g, label, offset(g, x, 11), offset(g, y, 47), 0.94, tint)
    mood = words(g, g.eq(g.arr("Temper", index), 1), "нервный", "спокойный")
    mood = words(g, tilting, "ТИЛЬТ", mood)
    show_mood = g.both(enabled, g.both(g.negate(is_free), g.negate(is_broken)))
    text(g, words(g, show_mood, mood, ""), offset(g, x, 11), offset(g, y, 68), 0.79, MUTED)
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
    text(g, g.get("Status"), 858, offset(g, y, 39), 0.84, g.get("Tint"))


def queue_label(g, member, selection):
    left = g.get(member)
    selected = g.eq(g.get("Guest"), selection)
    timer = g.append(g.string(g.div(g.add(left, 9), 10)), " сек.")
    status = g.append(words(g, selected, "Выбран · ", "Ждёт · "), timer)
    return words(g, g.gt(left, 0), status, "Очередь пуста")


def floor_objects(g):
    for desk in range(8):
        g.call("DrawDesk", Desk=desk, Left=244.0 + 146.0 * (desk % 4), Top=187.0 + 190.0 * (desk // 4))
    for index, top, title, status, tint in (
        (10, 189.0, "Спокойный гость", queue_label(g, "WaitCalm", 1), TEAL),
        (11, 266.0, "Нервный гость", queue_label(g, "WaitNervous", 2), VIOLET),
        (12, 357.0, "Холодильник", "Энергетики", BLUE),
        (13, 445.0, "Склад", "Запасные мыши", VIOLET),
    ):
        g.call("DrawStation", Station=index, Left=44.0, Top=top, Title=title, Status=status, Tint=tint)
    off = g.gt(g.get("ServerDown"), 0)
    g.call("DrawRight", Station=14, Top=187.0, Title="Сервер", Status=words(g, off, "Оффлайн", "В сети"),
           Tint=color_when(g, off, PINK, TEAL))
    g.call("DrawRight", Station=15, Top=400.0, Title="Снэк-бар",
           Status=words(g, g.eq(g.get("ShiftNo"), 1), "Закрыт", "Перекус"), Tint=AMBER)


def draw_player(g):
    x, y = g.get("PlayerX"), g.get("PlayerY")
    rect(g, offset(g, x, -11), offset(g, y, -11), 22, 22, INSET)
    rect(g, offset(g, x, -8), offset(g, y, -8), 16, 16, TEAL)
    rect(g, offset(g, x, -4), offset(g, y, -4), 8, 8, WHITE)
    item = g.get("HeldItem")
    cargo = words(g, g.eq(item, 1), "Энергетик", words(g, g.eq(item, 2), "Мышь", words(g, g.eq(item, 3), "Перекус", "Пусто")))
    text(g, g.append("Предмет  /  ", cargo), 29, 572, 1.09, TEAL)
    text(g, "WASD  идти     E  взаимодействовать / удерживать     F  успокоить     Q  освободить руки", 275, 574, 0.9, WHITE)
    limit = g.call("InteractDuration", result="Value")
    g.guard(g.gt(g.get("HoldTime"), 0.0, True))
    g.guard(g.gt(limit, 0.0, True))
    rect(g, offset(g, x, -23), offset(g, y, 16), 46, 5, INSET)
    progress = g.clamp(g.div(g.get("HoldTime"), limit, True), 0.0, 1.0)
    rect(g, offset(g, x, -23), offset(g, y, 16), g.mul(progress, 46.0, True), 5, AMBER)


def overlay(g):
    phase = g.get("Phase")
    intro = g.eq(phase, 0)
    won = g.either(g.eq(phase, 2), g.eq(phase, 4))
    rect(g, 30, 105, 940, 446, OVERLAY)
    panel(g, 218, 159, 565, 322)
    rect(g, 218, 159, 565, 4, color_when(g, intro, BLUE, color_when(g, won, TEAL, PINK)))
    title = words(g, g.eq(phase, 4), "Три смены закрыты", words(g, won, "План выполнен", "Смена провалена"))
    text(g, words(g, intro, "Дневной админ ушёл.", title), 247, 188, 2.2)
    summary = g.branch(intro)
    text(g, "До 06:00 клуб на тебе. Посади гостей, обслужи ряд и спаси рейтинг.", 249, 249, 0.98, MUTED)
    text(g, "1. Подойди к гостю в очереди и нажми E.", 249, 289, 1.04)
    text(g, "2. Выбери свободный ПК и нажми E снова.", 249, 319, 1.04)
    text(g, "3. Красная шкала — тильт. Рядом с гостем нажми F.", 249, 349, 1.04)
    text(g, "ENTER   Начать смену", 249, 421, 1.25, TEAL)
    g.resume(summary)
    text(g, g.append("Выручка   ", g.string(g.get("Cash")), " / ", g.string(g.get("Goal"))), 249, 248, 1.18, TEAL)
    text(g, g.append("Рейтинг   ", g.string(g.get("Rating")), " / 5"), 249, 280, 1.12, AMBER)
    text(g, g.append("Ушли в ярости   ", g.string(g.get("Lost")), "     Обслужено   ", g.string(g.get("Served"))), 249, 314, 1.06)
    prompt = words(g, g.eq(phase, 4), "Начать заново", words(g, won, "Следующая смена", "Повторить смену"))
    text(g, g.append("ENTER   ", prompt), 249, 421, 1.25, TEAL)


def draw_frame(g):
    width, height = as_real(g, g.get("Width")), as_real(g, g.get("Height"))
    g.set("UiScale", g.math("FMin", A=g.div(width, 1000.0, True), B=g.div(height, 620.0, True)))
    g.set("OriginX", g.mul(g.sub(width, scale(g, 1000.0), True), 0.5, True))
    g.set("OriginY", g.mul(g.sub(height, scale(g, 620.0), True), 0.5, True))
    g.invoke("HUD.DrawRect", RectColor=BG, ScreenX=0, ScreenY=0, ScreenW=width, ScreenH=height)
    g.call("DrawBoard")
    intro = g.branch(g.gt(g.get("Phase"), 0))
    g.call("DrawFloorObjects")
    g.call("DrawPlayer")
    g.guard(g.gt(g.get("Phase"), 1))
    g.call("DrawOverlay")
    g.resume(intro)
    g.call("DrawOverlay")


XY = (("Left", "real"), ("Top", "real"))
LABEL = (("Title", "string"), ("Status", "string"), ("Tint", "color"))
SCREEN_GRAPHS = (
    ("DrawBoard", board, ()), ("DrawDesk", desk_card, (("Desk", "int"),) + XY),
    ("DrawStation", station, (("Station", "int"),) + XY + LABEL),
    ("DrawRight", station_right, (("Station", "int"), ("Top", "real")) + LABEL),
    ("DrawFloorObjects", floor_objects, ()), ("DrawPlayer", draw_player, ()),
    ("DrawOverlay", overlay, ()), ("DrawFrame", draw_frame, (("Width", "int"), ("Height", "int"))),
)
