from enum import IntEnum


class SignClass(IntEnum):
    """Klasy znaków drogowych. MUSZĄ być zgodne z enum SignClass w traffic_signs.proto.

    Test synchronizacji: tests/test_domain.py
    """

    NONE = 0
    STOP = 1
    YIELD = 2
    SPEED_LIMIT = 3
    OTHER = 4


class Weather(IntEnum):
    """Warunki atmosferyczne. MUSZĄ być zgodne z enum Weather w traffic_signs.proto.

    Test synchronizacji: tests/test_domain.py
    """

    SUNNY = 0
    RAIN = 1
    FOG = 2
