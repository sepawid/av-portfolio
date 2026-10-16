from av_portfolio.domain import SignClass, Weather
from av_portfolio.proto import traffic_signs_pb2


def test_sign_class_matches_proto() -> None:
    for member in SignClass:
        assert member.value == getattr(traffic_signs_pb2, member.name), (
            f"{member.name} niezgodny z traffic_signs.proto"
        )


def test_weather_matches_proto() -> None:
    for member in Weather:
        assert member.value == getattr(traffic_signs_pb2, member.name), (
            f"{member.name} niezgodny z traffic_signs.proto"
        )
