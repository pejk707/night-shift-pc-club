"""Coordinates and actor tags shared by the club level and its Blueprint graphs."""

ADMIN_START = (-430, 135, 94)

CAMERA_TAG = "ClubView"
BENCH_TAGS = ("ClubBench1", "ClubBench2", "ClubBench3")
AC_TAGS = tuple((f"ClubAC{level}", f"ClubACVent{level}") for level in range(1, 4))

RECEPTION_TAG = "ClubStationReception"
STOCK_TAG = "ClubStationStock"
STOCK_WORKTOP_TAG = "ClubStationStockWorktop"
DRINKS_TAG = "ClubStationDrinks"
SERVER_TAG = "ClubStationServer"
SNACK_TAG = "ClubStationSnack"
PC_TAGS = tuple(f"ClubStationPC{index:02}" for index in range(1, 9))
SERVER_ALARM_TAGS = ("ClubServerAlarmRack1", "ClubServerAlarmRack2")
SERVER_LIGHT_TAGS = ("ClubServerAlarmLight1", "ClubServerAlarmLight2")
