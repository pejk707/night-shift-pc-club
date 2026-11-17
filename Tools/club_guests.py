"""Place the queue's actual visitors in the 3D scene and animate their routes."""

from blueprint_graph import ARRAY, SYSTEM
from club_rules import DESKS, I, LINE_SIZE, tagged_actors
from club_scene import GUEST_ENTRANCE_TAG, GUEST_QUEUE_TAGS, GUEST_SEAT_TAGS

VARIANTS = ("Teal", "Red", "Violet", "Green", "Brown", "Glasses")
MESH_COMPONENT = "/Script/Engine.SkeletalMeshComponent"
CAPACITY = DESKS + LINE_SIZE + 4
MAX_WAYPOINTS = 6
WALK_SPEED = 310.0
WAIT, SIT_BACK, SIT_FRONT, EXIT = range(4)
IDLE_CLIP, WALK_CLIP, SIT_CLIP = range(3)
RESET_INTS = {
    "QueueGuestIds": LINE_SIZE, "DeskGuestIds": DESKS,
    "GuestVariant": CAPACITY + 1, "GuestPathIndex": CAPACITY + 1, "GuestPathCount": CAPACITY + 1,
    "GuestArrival": CAPACITY + 1,
}
GUEST_VECTOR_ARRAYS = ("GuestAnchors", "GuestWaypoints")
GUEST_ACTOR_ARRAYS = ("GuestActors",)
GUEST_ANCHORS = GUEST_QUEUE_TAGS + GUEST_SEAT_TAGS + (GUEST_ENTRANCE_TAG,)
ENTRANCE_ANCHOR = len(GUEST_ANCHORS) - 1
GUEST_ID = (("GuestId", "int"),)
FRAME = (("FrameSeconds", "real"),)


def vector(g, x, y, z=0.0):
    return g.math("MakeVector", X=x, Y=y, Z=z)


def coords(g, value):
    return g.invoke("KismetMathLibrary.BreakVector", result=("X", "Y", "Z"), InVec=value)


def valid(g, actor):
    return g.invoke(SYSTEM + "IsValid", result="ReturnValue", Object=actor)


def component(g, actor):
    return g.invoke("Actor.GetComponentByClass", result="ReturnValue", target=actor, ComponentClass=MESH_COMPONENT)


def cache_guest_anchors(g):
    g.resize("GuestAnchors", len(GUEST_ANCHORS))
    for index, tag in enumerate(GUEST_ANCHORS):
        g.call("CacheGuestAnchor", Index=index, Tag=tag)


def cache_guest_anchor(g):
    matches = tagged_actors(g, g.get("Tag"))
    g.guard(g.gt(g.invoke(ARRAY + "Array_Length", result="ReturnValue", TargetArray=matches), 0))
    actor = g.invoke(ARRAY + "Array_Get", result="Item", TargetArray=matches, Index=0)
    location = g.invoke("Actor.K2_GetActorLocation", result="ReturnValue", target=actor)
    g.store("GuestAnchors", g.get("Index"), location)


def reset_guest_models(g):
    g.guard(g.get("Scene3D"))
    for index in range(1, CAPACITY + 1):
        g.call("RemoveGuestModel", GuestId=index)
    for member, count in (
        ("GuestActors", CAPACITY + 1), ("GuestWaypoints", (CAPACITY + 1) * MAX_WAYPOINTS), *RESET_INTS.items(),
    ):
        g.resize(member, 0)
        g.resize(member, count)


def remove_guest_model(g):
    index = g.get("GuestId")
    size = g.invoke(ARRAY + "Array_Length", result="ReturnValue", TargetArray=g.get("GuestActors"))
    g.guard(g.lt(index, size))
    actor = g.arr("GuestActors", index)
    g.guard(valid(g, actor))
    g.invoke("Actor.K2_DestroyActor", target=actor)
    g.store("GuestActors", index, "None")
    g.store("GuestPathCount", index, 0)


def mesh_path(variant, clip=""):
    name = "SK_Guest_" + variant + clip
    return f"/Game/NightShift/Art/Characters/Guest_{variant}/SkeletalMeshes/{name}.{name}"


def configure_guest_mesh(g):
    actor = g.arr("GuestActors", g.get("GuestId"))
    mesh = component(g, actor)
    variant = g.arr("GuestVariant", g.get("GuestId"))
    for index, name in enumerate(VARIANTS):
        other = g.branch(g.eq(variant, index))
        g.invoke("SkeletalMeshComponent.SetSkeletalMeshAsset", target=mesh, NewMesh=mesh_path(name))
        g.resume(other)


def play_guest_clip(g):
    index = g.get("GuestId")
    mesh = component(g, g.arr("GuestActors", index))
    variant = g.arr("GuestVariant", index)
    clip = g.get("Clip")
    for outfit, name in enumerate(VARIANTS):
        other = g.branch(g.eq(variant, outfit))
        for mode, suffix in ((IDLE_CLIP, "_Idle"), (WALK_CLIP, "_Walk"), (SIT_CLIP, "_Sit")):
            next_clip = g.branch(g.eq(clip, mode))
            g.invoke("SkeletalMeshComponent.PlayAnimation", target=mesh,
                     NewAnimToPlay=mesh_path(name, suffix), bLooping=True)
            g.resume(next_clip)
        g.resume(other)


def find_free_guest_id(g):
    for index in range(1, CAPACITY + 1):
        used = g.branch(g.negate(valid(g, g.arr("GuestActors", index))))
        g.ret(index)
        g.resume(used)
    g.ret(0)


def entrance(g):
    x, y, _ = coords(g, g.arr("GuestAnchors", ENTRANCE_ANCHOR))
    return vector(g, x, g.add(y, 53.0, True))


def assign_route(g, index, arrival, points):
    base = g.mul(index, MAX_WAYPOINTS)
    for step, location in enumerate(points):
        g.store("GuestWaypoints", g.add(base, step), location)
    g.store("GuestPathIndex", index, 0)
    g.store("GuestPathCount", index, len(points))
    g.store("GuestArrival", index, arrival)
    g.call("PlayGuestClip", GuestId=index, Clip=WALK_CLIP)


def move_guest_to_queue(g):
    index = g.get("GuestId")
    g.guard(g.gt(index, 0))
    x, y, _ = coords(g, g.arr("GuestAnchors", g.get("Slot")))
    assign_route(g, index, WAIT, (vector(g, x, y),))


def spawn_guest_model(g):
    g.guard(g.get("Scene3D"))
    index = g.call("FindFreeGuestId", result="Value")
    g.guard(g.gt(index, 0))
    transform = g.math("MakeTransform", Location=entrance(g))
    deferred = g.invoke("GameplayStatics.BeginDeferredActorSpawnFromClass", result="ReturnValue",
                        ActorClass="/Script/Engine.SkeletalMeshActor", SpawnTransform=transform,
                        CollisionHandlingOverride="AlwaysSpawn")
    g.guard(valid(g, deferred))
    actor = g.invoke("GameplayStatics.FinishSpawningActor", result="ReturnValue",
                     Actor=deferred, SpawnTransform=transform)
    g.invoke("Actor.SetActorEnableCollision", target=actor, bNewActorEnableCollision=False)
    g.invoke("Actor.SetActorScale3D", target=actor, NewScale3D="(X=0.88,Y=0.88,Z=0.88)")
    g.store("GuestActors", index, actor)
    g.store("GuestVariant", index, g.mod(g.sub(g.get("ArrivalNo"), 1), len(VARIANTS)))
    g.call("ConfigureGuestMesh", GuestId=index)
    g.store("QueueGuestIds", g.get("Slot"), index)
    g.call("MoveGuestToQueue", GuestId=index, Slot=g.get("Slot"))


def advance_guest_models(g):
    g.guard(g.get("Scene3D"))
    g.store("QueueGuestIds", 0, g.arr("QueueGuestIds", 1))
    g.store("QueueGuestIds", 1, 0)
    g.call("MoveGuestToQueue", GuestId=g.arr("QueueGuestIds", 0), Slot=0)


def seat_guest_model(g):
    g.guard(g.get("Scene3D"))
    index = g.arr("QueueGuestIds", 0)
    g.guard(g.gt(index, 0))
    desk = g.get("Desk")
    g.store("DeskGuestIds", desk, index)
    chair = g.arr("GuestAnchors", g.add(desk, LINE_SIZE))
    x, y, z = coords(g, chair)
    far = g.lt(desk, 4)
    arrival = g.choose(far, SIT_BACK, SIT_FRONT)
    short_of_chair = g.add(y, g.choose(far, 59.0, -59.0, "Float"), True)
    assign_route(g, index, arrival, (
        vector(g, -418.0, 132.0), vector(g, -418.0, 0.0), vector(g, x, 0.0),
        vector(g, x, short_of_chair), vector(g, x, y, z),
    ))


def leave_guest_queue(g):
    g.guard(g.get("Scene3D"))
    slot = g.get("Slot")
    index = g.arr("QueueGuestIds", slot)
    g.guard(g.gt(index, 0))
    actor = g.arr("GuestActors", index)
    location = g.invoke("Actor.K2_GetActorLocation", result="ReturnValue", target=actor)
    _, y, _ = coords(g, location)
    assign_route(g, index, EXIT, (
        vector(g, -554.0, g.clamp(y, 149.0, 446.0)), vector(g, -554.0, 448.0), entrance(g),
    ))
    g.store("QueueGuestIds", slot, 0)


def leave_guest_desk(g):
    g.guard(g.get("Scene3D"))
    desk = g.get("Desk")
    index = g.arr("DeskGuestIds", desk)
    g.guard(g.gt(index, 0))
    location = g.invoke("Actor.K2_GetActorLocation", result="ReturnValue", target=g.arr("GuestActors", index))
    x, _, _ = coords(g, location)
    assign_route(g, index, EXIT, (
        vector(g, x, 0.0), vector(g, -418.0, 0.0), vector(g, -418.0, 132.0),
        vector(g, -554.0, 150.0), vector(g, -554.0, 448.0), entrance(g),
    ))
    g.store("DeskGuestIds", desk, 0)


def rotate_guest(g, actor, yaw):
    rotation = g.math("MakeRotator", Yaw=yaw)
    g.invoke("Actor.K2_SetActorRotation", target=actor, NewRotation=rotation, bTeleportPhysics=True)


def finish_guest_path(g):
    index = g.get("GuestId")
    arrival = g.arr("GuestArrival", index)
    staying = g.branch(g.eq(arrival, EXIT))
    g.call("RemoveGuestModel", GuestId=index)
    g.resume(staying)
    face = g.choose(g.eq(arrival, SIT_FRONT), 0.0, -180.0, "Float")
    rotate_guest(g, g.arr("GuestActors", index), face)
    g.call("PlayGuestClip", GuestId=index, Clip=g.choose(g.eq(arrival, WAIT), IDLE_CLIP, SIT_CLIP))


def step_guest_motion(g):
    index, dt = g.get("GuestId"), g.get("FrameSeconds")
    count, step = g.arr("GuestPathCount", index), g.arr("GuestPathIndex", index)
    g.guard(g.lt(step, count))
    actor = g.arr("GuestActors", index)
    g.guard(valid(g, actor))
    current = g.invoke("Actor.K2_GetActorLocation", result="ReturnValue", target=actor)
    target = g.arr("GuestWaypoints", g.add(g.mul(index, MAX_WAYPOINTS), step))
    distance = g.math("Vector_Distance", V1=current, V2=target)
    traveling = g.branch(g.negate(g.gt(distance, g.mul(dt, WALK_SPEED, True), True)))
    g.invoke("Actor.K2_SetActorLocation", target=actor, NewLocation=target, bSweep=False, bTeleport=True)
    g.store("GuestPathIndex", index, g.add(step, 1))
    g.guard(g.eq(g.arr("GuestPathIndex", index), count))
    g.call("FinishGuestPath", GuestId=index)
    g.resume(traveling)
    facing = g.math("FindLookAtRotation", Start=current, Target=target)
    yaw = g.invoke("KismetMathLibrary.BreakRotator", result="Yaw", InRot=facing)
    rotate_guest(g, actor, g.sub(yaw, 90.0, True))
    position = g.math("VInterpTo_Constant", Current=current, Target=target, DeltaTime=dt, InterpSpeed=WALK_SPEED)
    g.invoke("Actor.K2_SetActorLocation", target=actor, NewLocation=position, bSweep=False, bTeleport=True)


def update_guest_models(g):
    active = g.both(g.get("Scene3D"), g.eq(g.get("Phase"), 1))
    paused = g.either(g.get("ShopOpen"), g.get("RepairOpen"))
    g.guard(g.both(active, g.negate(paused)))
    for index in range(1, CAPACITY + 1):
        g.call("StepGuestMotion", GuestId=index, FrameSeconds=g.clamp(g.get("FrameSeconds"), 0.0, 0.05))


GUEST_GRAPHS = (
    ("CacheGuestAnchors", cache_guest_anchors, ()),
    ("CacheGuestAnchor", cache_guest_anchor, (("Index", "int"), ("Tag", "name"))),
    ("ResetGuestModels", reset_guest_models, ()),
    ("RemoveGuestModel", remove_guest_model, GUEST_ID),
    ("FindFreeGuestId", find_free_guest_id, (), "int"),
    ("ConfigureGuestMesh", configure_guest_mesh, GUEST_ID),
    ("PlayGuestClip", play_guest_clip, GUEST_ID + (("Clip", "int"),)),
    ("SpawnGuestModel", spawn_guest_model, (("Slot", "int"),)),
    ("MoveGuestToQueue", move_guest_to_queue, GUEST_ID + (("Slot", "int"),)),
    ("AdvanceGuestModels", advance_guest_models, ()),
    ("SeatGuestModel", seat_guest_model, I),
    ("LeaveGuestQueue", leave_guest_queue, (("Slot", "int"),)),
    ("LeaveGuestDesk", leave_guest_desk, I),
    ("StepGuestMotion", step_guest_motion, GUEST_ID + FRAME),
    ("FinishGuestPath", finish_guest_path, GUEST_ID),
    ("UpdateGuestModels", update_guest_models, FRAME),
)
