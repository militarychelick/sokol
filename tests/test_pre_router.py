# -*- coding: utf-8 -*-
from sokol.pre_router import PreRouter


def test_prerouter_open_app():
    a = PreRouter.route("открой блокнот")
    assert a is not None
    assert a.get("type") in ("launch_app", "system_tool")


def test_prerouter_help():
    a = PreRouter.route("справка")
    assert a == {"type": "help"}


def test_prerouter_volume_set():
    a = PreRouter.route("громкость 50")
    assert a is not None
    assert a.get("type") == "volume_set"
    assert a.get("params", {}).get("percent") == 50


def test_prerouter_none_for_chatty():
    a = PreRouter.route("расскажи длинную историю про космос без команд")
    assert a is None
