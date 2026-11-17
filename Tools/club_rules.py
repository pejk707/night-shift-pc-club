"""Emit the playable shift, visitors, and station interactions as K2 graphs."""

from typing import NamedTuple

from blueprint_graph import ARRAY, SYSTEM
from club_scene import (
    AC_TAGS, ADMIN_START, BENCH_TAGS, CAMERA_TAG, DRINKS_SIDE_TAG, DRINKS_TAG, PC_DESK_TAGS, PC_TAGS, RECEPTION_TAG,
    SERVER_ALARM_TAGS, SERVER_LIGHT_TAGS, SERVER_TAG, SNACK_TAG, STOCK_TAG, STOCK_WORKTOP_TAG,
)

DESKS = 8
DURATION = 3600  # 0.1-second steps
FREE, PLAYING, ENERGY, CRASH, BROKEN, PIZZA = range(6)
NONE, DRINK, MOUSE, SLICE = range(4)
RECEPTION, FRIDGE, STOCK, SERVER, KITCHEN = 10, 12, 13, 14, 15
NO_SERVICE_PANEL, DRINK_PANEL, PC_PANEL = range(3)
DRINK_NAMES = ("Цитрус", "Ягоды", "Без сахара")
GAME_FROZEN, LAUNCHER_FROZEN = range(2)
NO_SLICE, HEATING, HOT, COLD = range(4)
# Seconds from request creation, at normal pace and at maximum pressure.
REQUEST_BUDGETS = {CRASH: (40, 30), ENERGY: (55, 45), PIZZA: (70, 60)}
SCENE_STATIONS = (
    *((index, tag, 86.0, 84.0) for index, tag in enumerate(PC_TAGS)),
    (RECEPTION, RECEPTION_TAG, 126.0, 66.0),
    (FRIDGE, DRINKS_TAG, 88.0, 67.0),
    (STOCK, STOCK_TAG, 80.0, 63.0),
    (STOCK, STOCK_WORKTOP_TAG, 58.0, 66.0),
    (SERVER, SERVER_TAG, 125.0, 76.0),
    (KITCHEN, SNACK_TAG, 112.0, 80.0),
    (FRIDGE, DRINKS_SIDE_TAG, 74.0, 88.0),
)
CALM, NERVOUS = 1, 2
LINE_SIZE = 2
SUPPLIES_NIGHT = 2
BELL_PATH = "/Game/NightShift/Audio/S_DoorBell"
MAX_UPGRADE_LEVEL = 3


class Upgrade(NamedTuple):
    key: str
    member: str
    title: str
    prices: tuple[int, ...]
    effect: str
    values: tuple[int, ...]
    unit: str


AIR_CONDITIONER = Upgrade("One", "AirConditionerLevel", "Кондиционер", (500, 800, 1150),
                          "Замедление потери терпения за ПК", (0, 25, 35, 45), "%")
BENCH = Upgrade("Two", "BenchLevel", "Скамейка", (350, 550, 800),
                "Дополнительное ожидание в очереди", (0, 10, 18, 25), " с")
REPAIR_KIT = Upgrade("Three", "RepairKitLevel", "Набор для ремонта", (650, 900, 1250),
                     "Сокращение времени перезапуска ПК", (0, 35, 45, 55), "%")
PARTITIONS = Upgrade("Four", "PartitionsLevel", "Шумозащитные перегородки", (450, 700, 1000),
                      "Снижение потерь от тильта соседей", (0, 1, 2, 3), " ед. за тик")
PAYMENT_TERMINAL = Upgrade("Five", "TerminalLevel", "Терминал оплаты", (550, 850, 1200),
                           "Доплата за посадку гостя", (0, 20, 35, 50), "")
UPGRADES = (AIR_CONDITIONER, BENCH, REPAIR_KIT, PARTITIONS, PAYMENT_TERMINAL)

DESK_ARRAYS = ("DeskState", "Patience", "Temper", "NextRequest", "Departure", "Calmed", "WasTilting",
               "RequestRemaining", "RequestRate", "RequestVariant", "RecoveryStage", "RestartUntil")
LINE_ARRAYS = ("LineMood", "LineWait")
INT_DEFAULTS = dict(ShiftNo=1, Phase=0, Rating=5, Cash=0, Lost=0, Served=0, Goal=2200,
                    Places=6, Step=0, NextArrival=0, ArrivalNo=0, Guest=0, HeldItem=0,
                    Focus=-1, HoldFocus=-1, ServerDown=0, OrderRoll=0, Bank=0, Spent=0)
INT_DEFAULTS.update({upgrade.member + suffix: 0 for upgrade in UPGRADES for suffix in ("", "AtStart")})
REAL_DEFAULTS = dict(PlayerX=211.0, PlayerY=317.0, HoldTime=0.0,
                     UiScale=1.0, OriginX=0.0, OriginY=0.0, FocusDistance=0.0)
BOOL_DEFAULTS = dict(ActionDone=False, ShopOpen=False, Scene3D=False, SceneWalking=False)
SCENE_ARRAYS = ("SceneCenterX", "SceneCenterY", "SceneRadiusX", "SceneRadiusY")


def max_int(g, a, b):
    return g.math("Max", A=a, B=b)


def min_int(g, a, b):
    return g.math("Min", A=a, B=b)


def ceil_div(g, units, divisor):
    rounding = divisor - 1 if isinstance(divisor, int) else g.sub(divisor, 1)
    return g.div(g.add(units, rounding), divisor)


def rand(g, a, b):
    return g.math("RandomIntegerInRange", Min=a, Max=b)


def request_budget(g, state, *, minimum=False):
    budget = 1
    for kind, durations in REQUEST_BUDGETS.items():
        budget = g.choose(g.eq(state, kind), durations[minimum], budget)
    return budget


def reset_shift(g):
    night = g.get("ShiftNo")
    presets = {"Phase": 1, "Rating": 5, "Cash": 0, "Lost": 0, "Served": 0, "Step": 0,
               "NextArrival": 5, "ArrivalNo": 0, "Spent": 0, "ShopOpen": False,
               "Guest": 0, "HeldItem": 0, "Focus": -1, "HoldFocus": -1,
               "ServerDown": 0, "ActionDone": False, "HoldTime": 0.0,
               "PlayerX": 211.0, "PlayerY": 317.0,
               "Places": g.add(night, 5), "Goal": g.add(1300, g.mul(night, 900))}
    for member, value in presets.items():
        g.set(member, value)
    for upgrade in UPGRADES:
        g.set(upgrade.member + "AtStart", g.get(upgrade.member))
    for array, size in [(name, DESKS) for name in DESK_ARRAYS] + [(name, LINE_SIZE) for name in LINE_ARRAYS]:
        g.resize(array, 0)
        g.resize(array, size)
    g.call("ResetGuestModels")
    g.call("CloseRepair")
    g.call("ResetService")
    g.call("SyncServerAlarm")
    g.guard(g.get("Scene3D"))
    start = g.math("MakeVector", X=ADMIN_START[0], Y=ADMIN_START[1], Z=ADMIN_START[2])
    g.invoke("Actor.K2_SetActorLocation", target=player_pawn(g), NewLocation=start, bSweep=False, bTeleport=True)
    g.call("SyncSceneUpgrades")


def wallet(g):
    return g.add(g.get("Bank"), g.sub(g.get("Cash"), g.get("Spent")))


def value_at_level(g, level, values):
    value = values[0]
    for index, next_value in enumerate(values[1:]):
        value = g.choose(g.gt(level, index), next_value, value)
    return value


def upgrade_effect(g, upgrade):
    return value_at_level(g, g.get(upgrade.member), upgrade.values)


def continue_game(g):
    phase = g.get("Phase")
    night = g.get("ShiftNo")
    g.guard(g.negate(g.eq(phase, 1)))
    next_night = g.eq(phase, 2)
    retry = g.eq(phase, 3)
    new_campaign = g.eq(phase, 4)
    g.set("Bank", g.choose(new_campaign, 0, g.choose(next_night, wallet(g), g.get("Bank"))))
    for upgrade in UPGRADES:
        member = upgrade.member
        kept_level = g.choose(retry, g.get(member + "AtStart"), g.get(member))
        g.set(member, g.choose(new_campaign, 0, kept_level))
    g.set("ShiftNo", g.choose(new_campaign, 1, g.add(night, g.choose(next_night, 1, 0))))
    g.call("ResetShift")


def buy_upgrade(g):
    choice = g.get("Choice")
    for index, upgrade in enumerate(UPGRADES, start=1):
        other = g.branch(g.eq(choice, index))
        level = g.get(upgrade.member)
        g.guard(g.lt(level, MAX_UPGRADE_LEVEL))
        price = value_at_level(g, level, upgrade.prices)
        g.guard(g.negate(g.lt(wallet(g), price)))
        g.set("Spent", g.add(g.get("Spent"), price))
        g.set(upgrade.member, g.add(level, 1))
        g.call("SyncSceneUpgrades")
        g.resume(other)


def lose_guest(g):
    g.set("Lost", g.add(g.get("Lost"), 1))
    g.set("Rating", max_int(g, 0, g.sub(g.get("Rating"), 1)))


def advance_queue(g):
    for field in LINE_ARRAYS:
        g.store(field, 0, g.arr(field, 1))
        g.store(field, 1, 0)
    g.set("Guest", 0)
    g.call("AdvanceGuestModels")


def count_queue(g):
    slot = g.get("Slot")
    remaining = g.arr("LineWait", slot)
    g.guard(g.gt(remaining, 0))
    g.store("LineWait", slot, g.sub(remaining, 1))
    g.guard(g.eq(g.arr("LineWait", slot), 0))
    g.call("LeaveGuestQueue", Slot=slot)
    g.call("LoseGuest")
    tail = g.branch(g.eq(slot, 0))
    g.call("AdvanceQueue")
    g.resume(tail)
    g.store("LineMood", slot, 0)


def spawn_guest(g):
    step, night = g.get("Step"), g.get("ShiftNo")
    g.guard(g.negate(g.lt(step, g.get("NextArrival"))))
    extra = g.both(g.gt(step, 1220), g.lt(step, 2850))
    gap = g.sub(g.choose(extra, 235, 355), g.mul(night, 34))
    g.set("NextArrival", g.add(step, gap))
    g.guard(g.eq(g.arr("LineMood", 1), 0))
    g.set("ArrivalNo", g.add(g.get("ArrivalNo"), 1))
    calm = g.eq(g.mod(g.get("ArrivalNo"), 3), 1)
    # Set the timer first because writing the mood changes which slot is empty.
    slot = g.choose(g.eq(g.arr("LineMood", 0), 0), 0, 1)
    extra_wait = g.mul(upgrade_effect(g, BENCH), 10)
    g.store("LineWait", slot, g.add(g.choose(calm, 300, 240), extra_wait))
    g.call("SpawnGuestModel", Slot=slot)
    g.store("LineMood", slot, g.choose(calm, CALM, NERVOUS))
    g.invoke("GameplayStatics.PlaySound2D", Sound=BELL_PATH + ".S_DoorBell",
             VolumeMultiplier=0.65, bIsUISound=True)


def report_tilt(g):
    desk = g.get("Desk")
    state = g.arr("DeskState", desk)
    active = g.both(g.gt(state, PLAYING), g.negate(g.eq(state, BROKEN)))
    g.store("WasTilting", desk, g.choose(g.both(active, g.lt(g.arr("Patience", desk), 30)), 1, 0))


def wait_on_request(g):
    desk = g.get("Desk")
    state = g.arr("DeskState", desk)
    end_left = g.eq(g.mod(desk, 4), 0)
    end_right = g.eq(g.mod(desk, 4), 3)
    left = g.arr("WasTilting", max_int(g, 0, g.sub(desk, 1)))
    right = g.arr("WasTilting", min_int(g, 7, g.add(desk, 1)))
    spread = g.add(g.choose(end_left, 0, left), g.choose(end_right, 0, right))
    temper = g.arr("Temper", desk)
    # Calm guests are less affected, so their seat can interrupt a chain.
    tilt_penalty = g.choose(g.gt(spread, 0), g.add(1, g.mul(temper, 2)), 0)
    penalty = max_int(g, 0, g.sub(tilt_penalty, upgrade_effect(g, PARTITIONS)))
    server = g.choose(g.gt(g.get("ServerDown"), 0), 22, 0)
    calm = g.choose(g.eq(temper, 0), 8, 0)
    drain = g.add(g.sub(100, calm), g.add(g.mul(7, penalty), server))
    multiplier = g.sub(100, upgrade_effect(g, AIR_CONDITIONER))
    normal_seconds = request_budget(g, state)
    minimum_seconds = request_budget(g, state, minimum=True)
    # One second has ten steps. Normal drain consumes 100 units per step.
    # Cap the instantaneous rate so even uninterrupted pressure respects the deadline.
    cap = g.div(g.mul(normal_seconds, 100), minimum_seconds)
    rate = min_int(g, cap, g.div(g.mul(drain, multiplier), 100))
    g.store("RequestRate", desk, rate)
    g.store("RequestRemaining", desk, max_int(g, 0, g.sub(g.arr("RequestRemaining", desk), rate)))
    remaining = g.arr("RequestRemaining", desk)
    units_per_percent = g.mul(normal_seconds, 10)
    percent = ceil_div(g, remaining, units_per_percent)
    g.store("Patience", desk, min_int(g, 100, percent))
    g.guard(g.eq(remaining, 0))
    g.call("LeaveGuestDesk", Desk=desk)
    g.store("DeskState", desk, g.choose(g.lt(g.get("ShiftNo"), SUPPLIES_NIGHT), FREE, BROKEN))
    g.call("LoseGuest")


def new_order(g):
    desk = g.get("Desk")
    roll = rand(g, 0, 5)
    g.set("OrderRoll", roll)
    roll = g.get("OrderRoll")
    has_food = g.both(g.negate(g.lt(g.get("ShiftNo"), SUPPLIES_NIGHT)), g.gt(roll, 3))
    request = g.choose(has_food, PIZZA, g.choose(g.lt(roll, 2), CRASH, ENERGY))
    variant = g.choose(g.eq(request, ENERGY), rand(g, 0, len(DRINK_NAMES) - 1), roll)
    g.call("StartOrder", Desk=desk, Request=request, Variant=variant)


def start_order(g):
    desk, state = g.get("Desk"), g.get("Request")
    duration = request_budget(g, state)
    late = g.gt(g.add(g.get("Step"), g.mul(duration, 10)), DURATION)
    time_left = g.branch(late)
    g.store("NextRequest", desk, DURATION)
    g.resume(time_left)
    g.store("DeskState", desk, state)
    g.store("RequestVariant", desk, g.get("Variant"))
    g.store("RequestRemaining", desk, g.mul(duration, 1000))
    g.store("RequestRate", desk, 100)
    g.store("Patience", desk, 100)
    g.store("Calmed", desk, 0)
    g.store("RecoveryStage", desk, 0)
    g.store("RestartUntil", desk, 0)


def update_desk(g):
    desk, step = g.get("Desk"), g.get("Step")
    g.guard(g.lt(desk, g.get("Places")))
    state = g.arr("DeskState", desk)
    g.guard(g.both(g.gt(state, FREE), g.negate(g.eq(state, BROKEN))))
    playing = g.branch(g.gt(state, PLAYING))
    waiting = g.branch(g.both(g.eq(state, CRASH), g.gt(g.arr("RestartUntil", desk), 0)))
    g.call("FinishPcRecovery", Desk=desk)
    g.resume(waiting)
    g.call("WaitOnRequest", Desk=desk)
    g.resume(playing)
    new_task = g.branch(g.negate(g.lt(step, g.arr("Departure", desk))))
    g.call("LeaveGuestDesk", Desk=desk)
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
    g.call("SyncServerAlarm")


def shift_step(g):
    modal = g.either(g.get("ShopOpen"), g.get("RepairOpen"))
    g.guard(g.both(g.eq(g.get("Phase"), 1), g.negate(modal)))
    g.set("Step", g.add(g.get("Step"), 1))
    g.call("ServerFault")
    g.call("AdvanceMicrowave")
    for slot in reversed(range(LINE_SIZE)):
        g.call("CountQueue", Slot=slot)
    g.call("SpawnGuest")
    for desk in range(DESKS):
        g.call("ReportTilt", Desk=desk)
    for desk in range(DESKS):
        g.call("UpdateDesk", Desk=desk)
    valid = g.branch(g.eq(g.get("Rating"), 0))
    g.call("CloseServicePanel")
    g.set("Phase", 3)
    g.resume(valid)
    g.guard(g.negate(g.lt(g.get("Step"), DURATION)))
    g.call("CloseServicePanel")
    won = g.negate(g.lt(g.get("Cash"), g.get("Goal")))
    on_final_night = g.eq(g.get("ShiftNo"), 3)
    g.set("Phase", g.choose(won, g.choose(on_final_night, 4, 2), 3))


def seat_guest(g):
    desk = g.get("Desk")
    guest, step = g.get("Guest"), g.get("Step")
    g.guard(g.gt(guest, 0))
    nervous = g.eq(guest, NERVOUS)
    g.store("Temper", desk, g.choose(nervous, 1, 0))
    g.store("DeskState", desk, PLAYING)
    g.store("NextRequest", desk, g.add(step, rand(g, 65, 125)))
    g.store("Departure", desk, g.add(step, rand(g, 410, 530)))


def confirm_seat(g):
    g.guard(g.gt(g.get("Guest"), 0))
    g.call("SeatGuest", Desk=g.get("Desk"))
    g.call("SeatGuestModel", Desk=g.get("Desk"))
    g.call("AdvanceQueue")
    g.set("Cash", g.add(g.get("Cash"), g.add(155, upgrade_effect(g, PAYMENT_TERMINAL))))
    g.set("Served", g.add(g.get("Served"), 1))


def close_order(g):
    desk, step = g.get("Desk"), g.get("Step")
    g.store("DeskState", desk, PLAYING)
    g.store("RestartUntil", desk, 0)
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
    g.call("OpenPcPanel", Desk=desk)
    g.resume(next_action)
    next_action = g.branch(g.eq(state, BROKEN))
    g.guard(g.eq(g.get("HeldItem"), MOUSE))
    g.set("HeldItem", NONE)
    g.store("DeskState", desk, FREE)
    g.resume(next_action)
    correct_drink = g.both(g.eq(g.get("HeldItem"), DRINK),
                           g.eq(g.get("HeldDrink"), g.arr("RequestVariant", desk)))
    valid = g.either(g.both(g.eq(state, ENERGY), correct_drink),
                     g.both(g.eq(state, PIZZA), g.eq(g.get("HeldItem"), SLICE)))
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
    g.store("RequestRemaining", desk, g.mul(request_budget(g, state), 650))
    g.store("Calmed", desk, 1)


def interact(g):
    focus = g.get("Focus")
    g.guard(g.gt(focus, -1))
    station = g.branch(g.lt(focus, DESKS))
    g.call("ServiceDesk", Desk=focus)
    g.resume(station)
    other = g.branch(g.eq(focus, SERVER))
    g.guard(g.eq(g.get("ServerDown"), 1))
    g.call("OpenRepair")
    g.resume(other)
    other = g.branch(g.eq(focus, RECEPTION))
    g.set("Guest", g.arr("LineMood", 0))
    g.resume(other)
    gated_station = g.either(g.eq(focus, STOCK), g.eq(focus, KITCHEN))
    g.guard(g.negate(g.both(gated_station, g.lt(g.get("ShiftNo"), SUPPLIES_NIGHT))))
    other = g.branch(g.eq(focus, FRIDGE))
    g.call("OpenFridgePanel")
    g.resume(other)
    other = g.branch(g.eq(focus, KITCHEN))
    g.call("UseMicrowave")
    g.resume(other)
    g.guard(g.eq(g.get("HeldItem"), NONE))
    g.set("HeldItem", MOUSE)


def within(g, value, center, radius):
    return g.lt(g.math("Abs", A=g.sub(value, center, True)), radius, True)


def player_pawn(g):
    return g.invoke("GameplayStatics.GetPlayerPawn", result="ReturnValue", PlayerIndex=0)


def tagged_actors(g, tag):
    return g.invoke("GameplayStatics.GetAllActorsWithTag", result="OutActors", Tag=tag)


def apply_scene_movement(g):
    direction = g.math("MakeVector", X=g.get("AxisX"), Y=g.get("AxisY"), Z=0.0)
    g.invoke("Pawn.AddMovementInput", target=player_pawn(g), WorldDirection=direction)


def update_scene_animation(g):
    g.guard(g.get("Scene3D"))
    pawn = player_pawn(g)
    velocity = g.invoke("Actor.GetVelocity", target=pawn, result="ReturnValue")
    modal = g.either(g.either(g.get("ShopOpen"), g.get("RepairOpen")),
                    g.gt(g.get("ServicePanel"), NO_SERVICE_PANEL))
    active = g.both(g.eq(g.get("Phase"), 1), g.negate(modal))
    walking = g.both(active, g.gt(g.math("VSizeXY", A=velocity), 12.0, True))
    g.guard(g.math("BooleanXOR", A=walking, B=g.get("SceneWalking")))
    g.set("SceneWalking", walking)
    mesh = g.invoke("Actor.GetComponentByClass", result="ReturnValue", target=pawn,
                    ComponentClass="/Script/Engine.SkeletalMeshComponent")
    idle = g.branch(g.get("SceneWalking"))
    for clip in ("Walk", "Idle"):
        name = "SK_Admin_" + clip
        g.invoke("SkeletalMeshComponent.PlayAnimation", target=mesh, bLooping=True,
                 NewAnimToPlay=f"/Game/NightShift/Art/Characters/Admin/SkeletalMeshes/{name}.{name}")
        if clip == "Walk":
            g.resume(idle)


def move(g):
    delta = g.get("FrameSeconds")
    step = g.mul(g.clamp(delta, 0.0, 0.05), 252.0, True)
    left, right = g.key("A"), g.key("D")
    up, down = g.key("W"), g.key("S")
    dx = g.sub(g.choose(right, 1.0, 0.0, "Float"), g.choose(left, 1.0, 0.0, "Float"), True)
    dy = g.sub(g.choose(down, 1.0, 0.0, "Float"), g.choose(up, 1.0, 0.0, "Float"), True)
    map_view = g.branch(g.get("Scene3D"))
    g.call("ApplySceneMovement", AxisX=dx, AxisY=dy)
    g.resume(map_view)
    diagonal = g.both(g.math("BooleanXOR", A=left, B=right), g.math("BooleanXOR", A=up, B=down))
    step = g.mul(step, g.choose(diagonal, 0.7071068, 1.0, "Float"), True)
    g.set("PlayerX", g.clamp(g.add(g.get("PlayerX"), g.mul(dx, step, True), True), 40.0, 955.0))
    g.set("PlayerY", g.clamp(g.add(g.get("PlayerY"), g.mul(dy, step, True), True), 155.0, 550.0))


def find_focus(g):
    map_view = g.branch(g.get("Scene3D"))
    g.call("FindSceneFocus")
    g.resume(map_view)
    x, y = g.get("PlayerX"), g.get("PlayerY")
    col = g.math("FTrunc", A=g.div(g.sub(x, 240, True), 146, True))
    top = within(g, y, 245.0, 57.0)
    bottom = within(g, y, 435.0, 57.0)
    x_valid = g.both(g.gt(x, 240.0, True), g.lt(x, 824.0, True))
    desk = g.add(col, g.choose(top, 0, 4))
    g.set("Focus", g.choose(g.both(x_valid, g.either(top, bottom)), desk, -1))
    for index, sx, sy, rx, ry in ((RECEPTION, 117, 260, 79, 73),
                                 (FRIDGE, 110, 391, 67, 34), (STOCK, 110, 478, 67, 34),
                                 (SERVER, 910, 226, 55, 48), (KITCHEN, 910, 441, 55, 45)):
        hit = g.both(within(g, x, float(sx), float(rx)), within(g, y, float(sy), float(ry)))
        g.set("Focus", g.choose(hit, index, g.get("Focus")))


def find_scene_focus(g):
    location = g.invoke("Actor.K2_GetActorLocation", target=player_pawn(g), result="ReturnValue")
    x = g.invoke("KismetMathLibrary.BreakVector", result="X", InVec=location)
    y = g.invoke("KismetMathLibrary.BreakVector", result="Y", InVec=location)
    g.set("Focus", -1)
    g.set("FocusDistance", 1000000.0)
    for slot, (focus, _, _, _) in enumerate(SCENE_STATIONS):
        g.call("CheckSceneStation", Slot=slot, Station=focus, PlayerWorldX=x, PlayerWorldY=y)


def cache_scene_stations(g):
    for member in SCENE_ARRAYS:
        g.resize(member, len(SCENE_STATIONS))
    for slot, (_, tag, rx, ry) in enumerate(SCENE_STATIONS):
        g.call("CacheSceneStation", Slot=slot, Tag=tag, RadiusX=rx, RadiusY=ry)


def cache_scene_station(g):
    slot = g.get("Slot")
    matches = tagged_actors(g, g.get("Tag"))
    g.guard(g.gt(g.invoke(ARRAY + "Array_Length", result="ReturnValue", TargetArray=matches), 0))
    actor = g.invoke(ARRAY + "Array_Get", result="Item", TargetArray=matches, Index=0)
    location = g.invoke("Actor.K2_GetActorLocation", target=actor, result="ReturnValue")
    x, y = g.invoke("KismetMathLibrary.BreakVector", result=("X", "Y"), InVec=location)
    for member, value in zip(SCENE_ARRAYS, (x, y, g.get("RadiusX"), g.get("RadiusY"))):
        g.store(member, slot, value)


def cache_pc_status_anchors(g):
    g.resize("PcStatusAnchors", DESKS)
    for desk, tag in enumerate(PC_DESK_TAGS):
        # Place the statuses on the outside of each row, away from the main aisle.
        g.call("CachePcStatusAnchor", Desk=desk, Tag=tag, RowOffset=-150.0 if desk < 4 else 142.0)


def cache_pc_status_anchor(g):
    matches = tagged_actors(g, g.get("Tag"))
    g.guard(g.gt(g.invoke(ARRAY + "Array_Length", result="ReturnValue", TargetArray=matches), 0))
    desk = g.invoke(ARRAY + "Array_Get", result="Item", TargetArray=matches, Index=0)
    location = g.invoke("Actor.K2_GetActorLocation", target=desk, result="ReturnValue")
    x, y, z = g.invoke("KismetMathLibrary.BreakVector", result=("X", "Y", "Z"), InVec=location)
    anchor = g.math("MakeVector", X=x, Y=g.add(y, g.get("RowOffset"), True), Z=g.add(z, 72.0, True))
    g.store("PcStatusAnchors", g.get("Desk"), anchor)


def check_scene_station(g):
    slot = g.get("Slot")
    rx, ry = g.arr("SceneRadiusX", slot), g.arr("SceneRadiusY", slot)
    g.guard(g.gt(rx, 0.0, True))
    dx = g.sub(g.get("PlayerWorldX"), g.arr("SceneCenterX", slot), True)
    dy = g.sub(g.get("PlayerWorldY"), g.arr("SceneCenterY", slot), True)
    x_ratio, y_ratio = g.div(dx, rx, True), g.div(dy, ry, True)
    ellipse = g.add(g.mul(x_ratio, x_ratio, True), g.mul(y_ratio, y_ratio, True), True)
    distance = g.add(g.mul(dx, dx, True), g.mul(dy, dy, True), True)
    g.guard(g.both(g.lt(ellipse, 1.0, True), g.lt(distance, g.get("FocusDistance"), True)))
    g.set("Focus", g.get("Station"))
    g.set("FocusDistance", distance)


def set_scene_prop(g):
    matches = tagged_actors(g, g.get("Tag"))
    g.guard(g.gt(g.invoke(ARRAY + "Array_Length", result="ReturnValue", TargetArray=matches), 0))
    actor = g.invoke(ARRAY + "Array_Get", result="Item", TargetArray=matches, Index=0)
    shown = g.get("Shown")
    g.invoke("Actor.SetActorHiddenInGame", target=actor, bNewHidden=g.negate(shown))
    g.invoke("Actor.SetActorEnableCollision", target=actor, bNewActorEnableCollision=shown)


def sync_scene_upgrades(g):
    g.guard(g.get("Scene3D"))
    for upgrade, tiers in ((BENCH, tuple((tag,) for tag in BENCH_TAGS)), (AIR_CONDITIONER, AC_TAGS)):
        for level, tags in enumerate(tiers):
            for tag in tags:
                g.call("SetSceneProp", Tag=tag, Shown=g.gt(g.get(upgrade.member), level))


def set_server_light(g):
    matches = tagged_actors(g, g.get("Tag"))
    g.guard(g.gt(g.invoke(ARRAY + "Array_Length", result="ReturnValue", TargetArray=matches), 0))
    actor = g.invoke(ARRAY + "Array_Get", result="Item", TargetArray=matches, Index=0)
    light = g.invoke("Actor.GetComponentByClass", target=actor, result="ReturnValue",
                     ComponentClass="/Script/Engine.LightComponent")
    g.invoke("SceneComponent.SetVisibility", target=light, bNewVisibility=g.get("Active"))


def sync_server_alarm(g):
    g.guard(g.get("Scene3D"))
    alarm = g.eq(g.get("ServerDown"), 1)
    for tag in SERVER_ALARM_TAGS:
        g.call("SetSceneProp", Tag=tag, Shown=alarm)
    for tag in SERVER_LIGHT_TAGS:
        g.call("SetServerLight", Tag=tag, Active=alarm)


def interact_duration(g):
    focus = g.get("Focus")
    other = g.branch(g.both(g.gt(focus, -1), g.lt(focus, DESKS)))
    state = g.arr("DeskState", focus)
    g.ret(g.choose(g.eq(state, BROKEN), 0.55, 0.0, "Float"))
    g.resume(other)
    g.ret(0.0)


def handle_e(g):
    down = g.either(g.key("E"), g.key("E", just_pressed=True))
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
    g.call("UpdateSceneAnimation")
    g.call("UpdateGuestModels", FrameSeconds=g.get("FrameSeconds"))
    if_enter = g.key("Enter", just_pressed=True)
    playing = g.branch(g.eq(g.get("Phase"), 1))
    ordinary = g.branch(g.get("RepairOpen"))
    g.call("RepairInput")
    g.resume(ordinary)
    ordinary = g.branch(g.gt(g.get("ServicePanel"), NO_SERVICE_PANEL))
    g.call("ServicePanelInput")
    g.resume(ordinary)
    g.call("ShopInput")
    g.guard(g.negate(g.get("ShopOpen")))
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


def shop_input(g):
    no_toggle = g.branch(g.key("U", just_pressed=True))
    g.set("ShopOpen", g.negate(g.get("ShopOpen")))
    g.set("HoldTime", 0.0)
    g.set("HoldFocus", -1)
    g.set("ActionDone", True)
    g.resume(no_toggle)
    g.guard(g.get("ShopOpen"))
    for choice, upgrade in enumerate(UPGRADES, start=1):
        other = g.branch(g.key(upgrade.key, just_pressed=True))
        g.call("BuyUpgrade", Choice=choice)
        g.resume(other)


def start_simulation(g):
    cameras = tagged_actors(g, CAMERA_TAG)
    g.set("Scene3D", g.gt(g.invoke(ARRAY + "Array_Length", result="ReturnValue", TargetArray=cameras), 0))
    g.invoke(SYSTEM + "K2_SetTimer", FunctionName="ShiftStep",
             Time=0.1, bLooping=True)
    g.guard(g.get("Scene3D"))
    g.call("CacheSceneStations")
    g.call("CachePcStatusAnchors")
    g.call("CacheGuestAnchors")
    g.call("SyncServerAlarm")


I = (("Desk", "int"),)
DT = (("FrameSeconds", "real"),)
RULE_GRAPHS = (
    ("ResetShift", reset_shift, ()), ("ContinueGame", continue_game, ()), ("LoseGuest", lose_guest, ()),
    ("AdvanceQueue", advance_queue, ()), ("CountQueue", count_queue, (("Slot", "int"),)),
    ("SpawnGuest", spawn_guest, ()), ("ReportTilt", report_tilt, I), ("WaitOnRequest", wait_on_request, I),
    ("NewOrder", new_order, I), ("UpdateDesk", update_desk, I), ("ServerFault", server_fault, ()),
    ("StartOrder", start_order, I + (("Request", "int"), ("Variant", "int"))),
    ("ShiftStep", shift_step, ()), ("SeatGuest", seat_guest, I), ("ConfirmSeat", confirm_seat, I),
    ("CloseOrder", close_order, I + (("Reward", "int"),)), ("ServiceDesk", service_desk, I),
    ("CoolGuest", cool_guest, ()), ("Interact", interact, ()), ("MoveAdmin", move, DT),
    ("ApplySceneMovement", apply_scene_movement, (("AxisX", "real"), ("AxisY", "real"))),
    ("UpdateSceneAnimation", update_scene_animation, ()),
    ("FindSceneFocus", find_scene_focus, ()), ("SyncSceneUpgrades", sync_scene_upgrades, ()),
    ("CacheSceneStations", cache_scene_stations, ()),
    ("CacheSceneStation", cache_scene_station, (("Slot", "int"), ("Tag", "name"),
                                                ("RadiusX", "real"), ("RadiusY", "real"))),
    ("CachePcStatusAnchors", cache_pc_status_anchors, ()),
    ("CachePcStatusAnchor", cache_pc_status_anchor, I + (("Tag", "name"), ("RowOffset", "real"))),
    ("CheckSceneStation", check_scene_station, (("Slot", "int"), ("Station", "int"),
                                               ("PlayerWorldX", "real"), ("PlayerWorldY", "real"))),
    ("SetSceneProp", set_scene_prop, (("Tag", "name"), ("Shown", "bool"))),
    ("SyncServerAlarm", sync_server_alarm, ()),
    ("SetServerLight", set_server_light, (("Tag", "name"), ("Active", "bool"))),
    ("FindFocus", find_focus, ()), ("InteractDuration", interact_duration, (), "real"),
    ("HandleE", handle_e, DT), ("PlayerTick", player_tick, DT),
    ("ShopInput", shop_input, ()), ("BuyUpgrade", buy_upgrade, (("Choice", "int"),)),
)
