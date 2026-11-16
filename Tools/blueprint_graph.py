"""Small authoring helpers for the UE 5.8 Blueprint Editor API."""

import unreal

LIB = unreal.BlueprintEditorLibrary
EDIT = unreal.BlueprintGraphEditor
ENGINE = "/Script/Engine."
MATH = "KismetMathLibrary."
STR = "KismetStringLibrary."
ARRAY = "KismetArrayLibrary."
SYSTEM = "KismetSystemLibrary."


def pin_type(kind):
    if kind.endswith("[]"):
        return LIB.get_array_type(pin_type(kind[:-2]))
    if kind == "color":
        return LIB.get_struct_type(unreal.LinearColor.static_struct())
    return LIB.get_basic_type_by_name(kind)


def pin(node, name, output=False):
    result = (node.find_output_pin if output else node.find_input_pin)(name)
    if not result.is_valid():
        pins = node.list_output_pins() if output else node.list_input_pins()
        raise ValueError(f"{node.get_node_title()}: {name} missing; {[str(p.get_pin_name()) for p in pins]}")
    return result


def wire(target, value):
    if isinstance(value, unreal.BlueprintGraphPin):
        if not value.try_create_connection(target):
            raise ValueError(f"Cannot connect {value.get_pin_name()} ({value.get_pin_type_display_string()}) "
                             f"to {target.get_pin_name()} ({target.get_pin_type_display_string()})")
        return
    literal = str(value).lower() if isinstance(value, bool) else str(value)
    if not target.set_pin_value(literal):
        raise ValueError(f"Cannot set {target.get_pin_name()} ({target.get_pin_type_display_string()}) to {literal!r}")


class Graph:
    def __init__(self, editor):
        self.editor = editor
        self.cursor = None
        self.params = {}
        self.row = 0
        self.column = 0
        self.first_result = None

    def place(self, node, pure=False):
        if node is None:
            raise ValueError("The Blueprint API did not create the requested node")
        if pure:
            self.row += 1
            node.set_node_pos(unreal.IntPoint(self.column * 360, 180 + 150 * self.row))
        else:
            self.column += 1
            self.row = 0
            node.set_node_pos(unreal.IntPoint(self.column * 360, 0))
        return node

    def resume(self, execution):
        self.cursor = execution

    def invoke(self, name, *, result=None, native=True, target=None, **values):
        path = ENGINE + name if native else name
        node = self.editor.add_call_function_node(path)
        if not node:
            raise ValueError(f"Cannot create call to {path}")
        execution = node.find_execute_pin()
        self.place(node, pure=not execution.is_valid())
        if target is not None:
            wire(node.find_self_pin(), target)
        # Connecting typed values first resolves wildcard operator and array pins.
        for is_pin in (True, False):
            for key, value in values.items():
                if isinstance(value, unreal.BlueprintGraphPin) == is_pin:
                    wire(pin(node, key), value)
        if execution.is_valid():
            wire(execution, self.cursor)
            self.cursor = node.find_then_pin()
        return pin(node, result, True) if result else None

    def call(self, name, **values):
        return self.invoke(name, native=False, **values)

    def get(self, name):
        if name in self.params:
            return self.params[name]
        node = self.place(self.editor.add_get_member_variable_node(name), pure=True)
        return pin(node, name, True)

    def set(self, name, value):
        node = self.place(self.editor.add_set_member_variable_node(name))
        wire(pin(node, name), value)
        wire(node.find_execute_pin(), self.cursor)
        self.cursor = node.find_then_pin()

    def arr(self, name, index):
        return self.invoke(ARRAY + "Array_Get", result="Item", TargetArray=self.get(name), Index=index)

    def store(self, name, index, value):
        self.invoke(ARRAY + "Array_Set", TargetArray=self.get(name), Index=index, Item=value, bSizeToFit=False)

    def resize(self, name, size):
        self.invoke(ARRAY + "Array_Resize", TargetArray=self.get(name), Size=size)

    def branch(self, condition):
        node = self.place(self.editor.add_branch_node())
        wire(node.find_execute_pin(), self.cursor)
        wire(pin(node, "Condition"), condition)
        self.cursor = node.find_then_pin()
        return node.find_else_pin()

    def guard(self, condition):
        self.branch(condition)

    def ret(self, value):
        node = self.place(self.first_result or self.editor.add_return_node())
        self.first_result = None
        wire(pin(node, "Value"), value)
        execution = node.find_execute_pin()
        if execution.is_valid():
            wire(execution, self.cursor)

    def math(self, fn, **params):
        return self.invoke(MATH + fn, result="ReturnValue", **params)

    def op(self, operator, a, b, kind="Int"):
        return self.math(f"{operator}_{kind}{kind}", A=a, B=b)

    def add(self, a, b, real=False):
        return self.op("Add", a, b, "Double" if real else "Int")

    def sub(self, a, b, real=False):
        return self.op("Subtract", a, b, "Double" if real else "Int")

    def mul(self, a, b, real=False):
        return self.op("Multiply", a, b, "Double" if real else "Int")

    def div(self, a, b, real=False):
        return self.op("Divide", a, b, "Double" if real else "Int")

    def mod(self, a, b):
        return self.op("Percent", a, b)

    def eq(self, a, b):
        return self.op("EqualEqual", a, b)

    def lt(self, a, b, real=False):
        return self.op("Less", a, b, "Double" if real else "Int")

    def gt(self, a, b, real=False):
        return self.op("Greater", a, b, "Double" if real else "Int")

    def both(self, a, b):
        return self.math("BooleanAND", A=a, B=b)

    def either(self, a, b):
        return self.math("BooleanOR", A=a, B=b)

    def negate(self, a):
        return self.math("Not_PreBool", A=a)

    def choose(self, condition, yes, no, kind="Int"):
        return self.math("Select" + kind, A=yes, B=no, bPickA=condition)

    def string(self, number):
        return self.invoke(STR + "Conv_IntToString", result="ReturnValue", InInt=number)

    def append(self, *pieces):
        result = pieces[0]
        for next_piece in pieces[1:]:
            result = self.invoke(STR + "Concat_StrStr", result="ReturnValue", A=result, B=next_piece)
        return result

    def key(self, key_name, just_pressed=False):
        controller = self.invoke("HUD.GetOwningPlayerController", result="ReturnValue")
        name = "WasInputKeyJustPressed" if just_pressed else "IsInputKeyDown"
        return self.invoke("PlayerController." + name, result="ReturnValue", target=controller, Key=key_name)

    def clamp(self, value, low, high):
        return self.math("FClamp", Value=value, Min=low, Max=high)
