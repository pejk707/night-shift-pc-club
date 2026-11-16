"""Emit the playable shift, visitors, and station interactions as K2 graphs."""

from blueprint_graph import SYSTEM

DESKS = 8
DURATION = 3600  # 0.1-second steps
FREE, PLAYING, ENERGY, CRASH, BROKEN, FOOD = range(6)
NONE, DRINK, MOUSE, SNACK = range(4)
CALM_LINE, NERVOUS_LINE, FRIDGE, STOCK, SERVER, KITCHEN = range(10, 16)

ARRAYS = ("DeskState", "Patience", "Temper", "NextRequest", "Departure", "Calmed", "WasTilting")
INT_DEFAULTS = dict(ShiftNo=1, Phase=0, Rating=5, Cash=0, Lost=0, Served=0, Goal=2200,
                    Places=6, Step=0, NextArrival=0, ArrivalNo=0, WaitCalm=0, WaitNervous=0,
                    Guest=0, HeldItem=0, Focus=-1, HoldFocus=-1, ServerDown=0, OrderRoll=0)
REAL_DEFAULTS = dict(PlayerX=211.0, PlayerY=317.0, HoldTime=0.0,
                     UiScale=1.0, OriginX=0.0, OriginY=0.0)
BOOL_DEFAULTS = dict(ActionDone=False)


def max_int(g, a, b):
    return g.math("Max", A=a, B=b)


def min_int(g, a, b):
    return g.math("Min", A=a, B=b)


def rand(g, a, b):
    return g.math("RandomIntegerInRange", Min=a, Max=b)


def reset_shift(g):
    night = g.get("ShiftNo")
    presets = {"Phase": 1, "Rating": 5, "Cash": 0, "Lost": 0, "Served": 0, "Step": 0,
               "NextArrival": 5, "ArrivalNo": 0, "WaitCalm": 300, "WaitNervous": 0,
               "Guest": 0, "HeldItem": 0, "Focus": -1, "HoldFocus": -1,
               "ServerDown": 0, "ActionDone": False, "HoldTime": 0.0,
               "PlayerX": 211.0, "PlayerY": 317.0,
               "Places": g.add(night, 5), "Goal": g.add(1300, g.mul(night, 900))}
    for member, value in presets.items():
        g.set(member, value)
    for array in ARRAYS:
        g.resize(array, 0)
        g.resize(array, DESKS)


def continue_game(g):
    phase = g.get("Phase")
    g.guard(g.negate(g.eq(phase, 1)))
    g.set("ShiftNo", g.choose(g.eq(phase, 4), 1, g.add(g.get("ShiftNo"), g.choose(g.eq(phase, 2), 1, 0))))
    g.call("ResetShift")


def lose_guest(g):
    g.set("Lost", g.add(g.get("Lost"), 1))
    g.set("Rating", max_int(g, 0, g.sub(g.get("Rating"), 1)))


def count_queue(g):
    lane, guest = g.get("IsNervous"), g.get("Selection")
    for which, selection in (("WaitCalm", 1), ("WaitNervous", 2)):
        remaining = g.get(which)
        match = lane if selection == 2 else g.negate(lane)
        other = g.branch(match)
        g.guard(g.gt(remaining, 0))
        g.set(which, g.sub(remaining, 1))
        g.guard(g.eq(g.get(which), 0))
        g.set("Guest", g.choose(g.eq(guest, selection), 0, guest))
        g.call("LoseGuest")
        g.resume(other)


def spawn_guest(g):
    step, night = g.get("Step"), g.get("ShiftNo")
    g.guard(g.negate(g.lt(step, g.get("NextArrival"))))
    extra = g.both(g.gt(step, 1220), g.lt(step, 2850))
    gap = g.sub(g.choose(extra, 235, 355), g.mul(night, 34))
    g.set("NextArrival", g.add(step, gap))
    g.set("ArrivalNo", g.add(g.get("ArrivalNo"), 1))
    calm_available = g.eq(g.get("WaitCalm"), 0)
    nerve_available = g.eq(g.get("WaitNervous"), 0)
    calm_first = g.eq(g.mod(g.get("ArrivalNo"), 3), 0)
    choose_calm = g.both(calm_available, g.either(calm_first, g.negate(nerve_available)))
    nerve_path = g.branch(choose_calm)
    g.set("WaitCalm", 300)
    g.resume(nerve_path)
    g.guard(nerve_available)
    g.set("WaitNervous", 240)


def report_tilt(g):
    desk = g.get("Desk")
    state = g.arr("DeskState", desk)
    active = g.both(g.gt(state, PLAYING), g.negate(g.eq(state, BROKEN)))
    g.store("WasTilting", desk, g.choose(g.both(active, g.lt(g.arr("Patience", desk), 30)), 1, 0))


def wait_on_request(g):
    desk = g.get("Desk")
    end_left = g.eq(g.mod(desk, 4), 0)
    end_right = g.eq(g.mod(desk, 4), 3)
    left = g.arr("WasTilting", max_int(g, 0, g.sub(desk, 1)))
    right = g.arr("WasTilting", min_int(g, 7, g.add(desk, 1)))
    spread = g.add(g.choose(end_left, 0, left), g.choose(end_right, 0, right))
    temper = g.arr("Temper", desk)
    # Calm guests are less affected, so their seat can interrupt a chain.
    penalty = g.choose(g.gt(spread, 0), g.add(1, g.mul(temper, 2)), 0)
    server = g.choose(g.gt(g.get("ServerDown"), 0), 1, 0)
    g.store("Patience", desk, max_int(g, 0, g.sub(g.arr("Patience", desk), g.add(1, g.add(penalty, server)))))
    g.guard(g.eq(g.arr("Patience", desk), 0))
    g.store("DeskState", desk, BROKEN)
    g.call("LoseGuest")


def new_order(g):
    desk = g.get("Desk")
    roll = rand(g, 0, 5)
    g.set("OrderRoll", roll)
    roll = g.get("OrderRoll")
    has_food = g.both(g.gt(g.get("ShiftNo"), 1), g.gt(roll, 3))
    request = g.choose(has_food, FOOD, g.choose(g.lt(roll, 2), CRASH, ENERGY))
    g.store("DeskState", desk, request)
    g.store("Patience", desk, 100)
    g.store("Calmed", desk, 0)


def update_desk(g):
    desk, step = g.get("Desk"), g.get("Step")
    g.guard(g.lt(desk, g.get("Places")))
    state = g.arr("DeskState", desk)
    g.guard(g.both(g.gt(state, FREE), g.negate(g.eq(state, BROKEN))))
    playing = g.branch(g.gt(state, PLAYING))
    pace = g.choose(g.both(g.eq(g.arr("Temper", desk), 0), g.eq(g.mod(step, 4), 0)), 1, 0)
    g.guard(g.eq(pace, 0))
    g.call("WaitOnRequest", Desk=desk)
    g.resume(playing)
    new_task = g.branch(g.negate(g.lt(step, g.arr("Departure", desk))))
    g.store("DeskState", desk, FREE)
    g.resume(new_task)
    g.guard(g.negate(g.lt(step, g.arr("NextRequest", desk))))
    g.call("NewOrder", Desk=desk)


def server_fault(g):
    step, night = g.get("Step"), g.get("ShiftNo")
    first = g.eq(step, g.sub(1760, g.mul(night, 80)))
    later = g.both(g.gt(night, 1), g.eq(step, g.sub(3140, g.mul(night, 100))))
    g.guard(g.either(first, later))
    g.set("ServerDown", 1)


def shift_step(g):
    g.guard(g.eq(g.get("Phase"), 1))
    g.set("Step", g.add(g.get("Step"), 1))
    g.call("ServerFault")
    g.call("SpawnGuest")
    for flag, selection in ((False, 1), (True, 2)):
        g.call("CountQueue", IsNervous=flag, Selection=selection)
    for desk in range(DESKS):
        g.call("ReportTilt", Desk=desk)
    for desk in range(DESKS):
        g.call("UpdateDesk", Desk=desk)
    valid = g.branch(g.eq(g.get("Rating"), 0))
    g.set("Phase", 3)
    g.resume(valid)
    g.guard(g.negate(g.lt(g.get("Step"), DURATION)))
    won = g.negate(g.lt(g.get("Cash"), g.get("Goal")))
    on_final_night = g.eq(g.get("ShiftNo"), 3)
    g.set("Phase", g.choose(won, g.choose(on_final_night, 4, 2), 3))


def seat_guest(g):
    desk = g.get("Desk")
    guest, step = g.get("Guest"), g.get("Step")
    g.guard(g.gt(guest, 0))
    nervous = g.eq(guest, 2)
    g.store("Temper", desk, g.choose(nervous, 1, 0))
    g.store("DeskState", desk, PLAYING)
    g.store("NextRequest", desk, g.add(step, rand(g, 65, 125)))
    g.store("Departure", desk, g.add(step, rand(g, 410, 530)))
    clear_calm = g.branch(nervous)
    g.set("WaitNervous", 0)
    g.resume(clear_calm)
    g.set("WaitCalm", 0)


def confirm_seat(g):
    g.guard(g.gt(g.get("Guest"), 0))
    g.call("SeatGuest", Desk=g.get("Desk"))
    g.set("Guest", 0)
    g.set("Cash", g.add(g.get("Cash"), 155))
    g.set("Served", g.add(g.get("Served"), 1))


def close_order(g):
    desk, step = g.get("Desk"), g.get("Step")
    g.store("DeskState", desk, PLAYING)
    g.store("NextRequest", desk, g.add(step, rand(g, 135, 215)))
    g.set("Cash", g.add(g.get("Cash"), g.get("Reward")))


def service_desk(g):
    desk = g.get("Desk")
    g.guard(g.lt(desk, g.get("Places")))
    state = g.arr("DeskState", desk)
    next_action = g.branch(g.eq(state, FREE))
    g.call("ConfirmSeat", Desk=desk)
    g.resume(next_action)
    next_action = g.branch(g.eq(state, CRASH))
    g.call("CloseOrder", Desk=desk, Reward=45)
    g.resume(next_action)
    next_action = g.branch(g.eq(state, BROKEN))
    g.guard(g.eq(g.get("HeldItem"), MOUSE))
    g.set("HeldItem", NONE)
    g.store("DeskState", desk, FREE)
    g.resume(next_action)
    valid = g.either(g.both(g.eq(state, ENERGY), g.eq(g.get("HeldItem"), DRINK)),
                     g.both(g.eq(state, FOOD), g.eq(g.get("HeldItem"), SNACK)))
    g.guard(valid)
    g.set("HeldItem", NONE)
    g.call("CloseOrder", Desk=desk, Reward=g.choose(g.eq(state, ENERGY), 85, 110))


def cool_guest(g):
    desk = g.get("Focus")
    g.guard(g.both(g.gt(desk, -1), g.lt(desk, g.get("Places"))))
    state = g.arr("DeskState", desk)
    g.guard(g.both(g.gt(state, PLAYING), g.negate(g.eq(state, BROKEN))))
    g.guard(g.both(g.lt(g.arr("Patience", desk), 30), g.eq(g.arr("Calmed", desk), 0)))
    g.store("Patience", desk, 65)
    g.store("Calmed", desk, 1)


def interact(g):
    focus = g.get("Focus")
    g.guard(g.gt(focus, -1))
    station = g.branch(g.lt(focus, DESKS))
    g.call("ServiceDesk", Desk=focus)
    g.resume(station)
    other = g.branch(g.eq(focus, SERVER))
    g.guard(g.eq(g.get("ServerDown"), 1))
    g.set("ServerDown", 0)
    g.set("Cash", g.add(g.get("Cash"), 100))
    g.resume(other)
    other = g.branch(g.lt(focus, FRIDGE))
    calm = g.eq(focus, CALM_LINE)
    waiting = g.choose(calm, g.get("WaitCalm"), g.get("WaitNervous"))
    g.guard(g.gt(waiting, 0))
    g.set("Guest", g.choose(calm, 1, 2))
    g.resume(other)
    g.guard(g.negate(g.both(g.eq(focus, KITCHEN), g.eq(g.get("ShiftNo"), 1))))
    item = g.choose(g.eq(focus, FRIDGE), DRINK, g.choose(g.eq(focus, STOCK), MOUSE, SNACK))
    g.set("HeldItem", item)


def within(g, value, center, radius):
    return g.lt(g.math("Abs", A=g.sub(value, center, True)), radius, True)


def move(g):
    delta = g.get("FrameSeconds")
    step = g.mul(g.clamp(delta, 0.0, 0.05), 252.0, True)
    left, right = g.key("A"), g.key("D")
    up, down = g.key("W"), g.key("S")
    dx = g.sub(g.choose(right, 1.0, 0.0, "Float"), g.choose(left, 1.0, 0.0, "Float"), True)
    dy = g.sub(g.choose(down, 1.0, 0.0, "Float"), g.choose(up, 1.0, 0.0, "Float"), True)
    diagonal = g.both(g.math("BooleanXOR", A=left, B=right), g.math("BooleanXOR", A=up, B=down))
    step = g.mul(step, g.choose(diagonal, 0.7071068, 1.0, "Float"), True)
    g.set("PlayerX", g.clamp(g.add(g.get("PlayerX"), g.mul(dx, step, True), True), 40.0, 955.0))
    g.set("PlayerY", g.clamp(g.add(g.get("PlayerY"), g.mul(dy, step, True), True), 155.0, 550.0))


def find_focus(g):
    x, y = g.get("PlayerX"), g.get("PlayerY")
    col = g.math("FTrunc", A=g.div(g.sub(x, 240, True), 146, True))
    top = within(g, y, 245.0, 57.0)
    bottom = within(g, y, 435.0, 57.0)
    x_valid = g.both(g.gt(x, 240.0, True), g.lt(x, 824.0, True))
    desk = g.add(col, g.choose(top, 0, 4))
    g.set("Focus", g.choose(g.both(x_valid, g.either(top, bottom)), desk, -1))
    for index, sx, sy, rx, ry in ((CALM_LINE, 117, 222, 79, 34), (NERVOUS_LINE, 117, 299, 79, 34),
                                 (FRIDGE, 110, 391, 67, 34), (STOCK, 110, 478, 67, 34),
                                 (SERVER, 910, 226, 55, 48), (KITCHEN, 910, 441, 55, 45)):
        hit = g.both(within(g, x, float(sx), float(rx)), within(g, y, float(sy), float(ry)))
        g.set("Focus", g.choose(hit, index, g.get("Focus")))


def interact_duration(g):
    focus = g.get("Focus")
    other = g.branch(g.both(g.gt(focus, -1), g.lt(focus, DESKS)))
    state = g.arr("DeskState", focus)
    g.ret(g.choose(g.eq(state, CRASH), 0.85, g.choose(g.eq(state, BROKEN), 0.55, 0.0, "Float"), "Float"))
    g.resume(other)
    g.ret(g.choose(g.eq(focus, SERVER), 1.15, 0.0, "Float"))


def handle_e(g):
    down = g.key("E")
    released = g.branch(down)
    g.guard(g.negate(g.get("ActionDone")))
    same = g.eq(g.get("Focus"), g.get("HoldFocus"))
    g.set("HoldTime", g.choose(same, g.add(g.get("HoldTime"), g.get("FrameSeconds"), True), 0.0, "Float"))
    g.set("HoldFocus", g.get("Focus"))
    limit = g.call("InteractDuration", result="Value")
    g.guard(g.both(g.gt(g.get("Focus"), -1), g.negate(g.lt(g.get("HoldTime"), limit, True))))
    g.call("Interact")
    g.set("HoldTime", 0.0)
    g.set("ActionDone", True)
    g.resume(released)
    g.set("HoldTime", 0.0)
    g.set("HoldFocus", -1)
    g.set("ActionDone", False)


def player_tick(g):
    if_enter = g.key("Enter", just_pressed=True)
    playing = g.branch(g.eq(g.get("Phase"), 1))
    g.call("MoveAdmin", FrameSeconds=g.get("FrameSeconds"))
    g.call("FindFocus")
    do_not_drop = g.branch(g.key("Q", just_pressed=True))
    g.set("HeldItem", NONE)
    g.set("Guest", 0)
    g.resume(do_not_drop)
    no_cool = g.branch(g.key("F", just_pressed=True))
    g.call("CoolGuest")
    g.resume(no_cool)
    g.call("HandleE", FrameSeconds=g.get("FrameSeconds"))
    g.resume(playing)
    g.guard(if_enter)
    g.call("ContinueGame")


def start_simulation(g):
    g.invoke(SYSTEM + "K2_SetTimer", FunctionName="ShiftStep",
             Time=0.1, bLooping=True)


I = (("Desk", "int"),)
DT = (("FrameSeconds", "real"),)
RULE_GRAPHS = (
    ("ResetShift", reset_shift, ()), ("ContinueGame", continue_game, ()), ("LoseGuest", lose_guest, ()),
    ("CountQueue", count_queue, (("IsNervous", "bool"), ("Selection", "int"))),
    ("SpawnGuest", spawn_guest, ()), ("ReportTilt", report_tilt, I), ("WaitOnRequest", wait_on_request, I),
    ("NewOrder", new_order, I), ("UpdateDesk", update_desk, I), ("ServerFault", server_fault, ()),
    ("ShiftStep", shift_step, ()), ("SeatGuest", seat_guest, I), ("ConfirmSeat", confirm_seat, I),
    ("CloseOrder", close_order, I + (("Reward", "int"),)), ("ServiceDesk", service_desk, I),
    ("CoolGuest", cool_guest, ()), ("Interact", interact, ()), ("MoveAdmin", move, DT),
    ("FindFocus", find_focus, ()), ("InteractDuration", interact_duration, (), "real"),
    ("HandleE", handle_e, DT), ("PlayerTick", player_tick, DT),
)
