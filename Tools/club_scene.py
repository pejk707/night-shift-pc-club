"""Coordinates and actor tags shared by the club level and its Blueprint graphs."""

ADMIN_START = (-430, 135, 94)

CAMERA_TAG = "ClubView"
BENCH_TAGS = ("ClubBench1", "ClubBench2", "ClubBench3")
AC_TAGS = tuple((f"ClubAC{level}", f"ClubACVent{level}") for level in range(1, 4))

RECEPTION_TAG = "ClubStationReception"
STOCK_TAG = "ClubStationStock"
STOCK_WORKTOP_TAG = "ClubStationStockWorktop"
DRINKS_TAG = "ClubStationDrinks"
DRINKS_SIDE_TAG = "ClubStationDrinksSide"
SERVER_TAG = "ClubStationServer"
SNACK_TAG = "ClubStationSnack"
PC_TAGS = tuple(f"ClubStationPC{index:02}" for index in range(1, 9))
PC_DESK_TAGS = tuple(f"PC_{index:02}" for index in range(1, 9))
GUEST_SEAT_TAGS = tuple(f"ClubGuestSeat{index:02}" for index in range(1, 9))
GUEST_QUEUE_TAGS = ("ClubGuestQueue1", "ClubGuestQueue2")
GUEST_ENTRANCE_TAG = "ClubGuestEntrance"
SERVER_ALARM_TAGS = ("ClubServerAlarmRack1", "ClubServerAlarmRack2")
SERVER_LIGHT_TAGS = ("ClubServerAlarmLight1", "ClubServerAlarmLight2")
