"""Argument validation in the open_plugin / set_param executors."""
from __future__ import annotations

import pytest

from app import tools
from app.tools.routes import route_line


def test_open_plugin_validation() -> None:
    assert tools.queue_open_plugin({"plugin": "  "})["attached"] is False
    assert tools.queue_open_plugin({"plugin": "Channel EQ", "new_instance": True})["steps"] == [
        {"ax_open_plugin": "Channel EQ", "new": True}]
    assert tools.queue_open_plugin({"plugin": "Channel EQ", "new_instance": False})["steps"] == [
        {"ax_open_plugin": "Channel EQ"}]


@pytest.mark.parametrize("raw, want", [
    ("80", "80"), ("80hz", "80"), ("-18 dB", "-18"), ("2.5", "2.5"), ("On", "on"), ("disabled", "off"),
    (-18, "-18"), (4.0, "4"), (True, "on"),
    ("by -3", "by:-3"), ("by +2.5 dB", "by:2.5"), ("BY -0.5", "by:-0.5"),
])
def test_set_param_parses_value(raw, want) -> None:
    got = tools.queue_set_param({"plugin": "P", "param": "X", "value": raw})
    assert got["attached"] and got["steps"][0]["ax_set_param"]["value"] == want, (raw, got)


@pytest.mark.parametrize("bad", ["4:1", "loud", "", None, "by 3"])
def test_set_param_refuses_non_number(bad) -> None:
    got = tools.queue_set_param({"plugin": "P", "param": "X", "value": bad})
    assert got["attached"] is False and "plain number" in got["reason"], (bad, got)


def test_toggle_route_carries_the_wanted_state() -> None:
    route = "low latency monitoring mode"
    got = tools.queue_open_setting({"name": route, "state": "On"})
    assert got["attached"] and got["steps"] == [
        {"menu_path": ["Record", "Low Latency Monitoring Mode"], "want": "on"}]
    assert tools.queue_open_setting({"name": route})["steps"] == [
        {"menu_path": ["Record", "Low Latency Monitoring Mode"]}]          # no state: a plain flip
    assert tools.queue_open_setting({"name": route, "state": "maybe"})["attached"] is False


def test_state_is_refused_on_a_route_that_isnt_a_toggle() -> None:
    assert tools.queue_open_setting({"name": "metronome settings", "state": "on"})["attached"] is False


STEM_OPEN = {"context_menu": ["Stem Splitter…"], "on": "region", "or": ["Processing", "Stem Splitter…"],
             "opens": "Stem Splitter"}


def test_stem_splitter_without_stems_only_opens_the_sheet() -> None:
    got = tools.queue_open_setting({"name": "stem splitter"})
    assert got["attached"] and got["steps"] == [STEM_OPEN], got


@pytest.mark.parametrize("value", ["Vocals, Drums", "vocals and drums", "drum & vocal"])
def test_stem_splitter_ticks_exactly_the_named_stems(value) -> None:
    got = tools.queue_open_setting({"name": "stem splitter", "value": value})
    assert got["attached"] and got["steps"] == [STEM_OPEN, {"checks": {
        "Vocals": True, "Drums": True, "Bass": False, "Guitar": False, "Piano": False, "Other": False},
        "sheet": "Stem Splitter"}], got
    assert got["checks"] == ["Vocals", "Drums"]


@pytest.mark.parametrize("value", ["strings", "vocals, synths"])
def test_stem_splitter_refuses_an_unknown_stem(value) -> None:
    got = tools.queue_open_setting({"name": "stem splitter", "value": value})
    assert got["attached"] is False and "Vocals, Drums, Bass" in got["reason"], got


def test_stem_splitter_route_line_offers_the_stems() -> None:
    line = route_line("stem splitter", tools.ROUTES["stem splitter"])
    assert "Control-click the region > Stem Splitter…" in line and "Vocals | Drums" in line, line
    assert "[target: region" in line, line


def test_stem_splitter_carries_the_named_region() -> None:
    got = tools.queue_open_setting({"name": "stem splitter", "target": " SICKO MODE ", "value": "vocals"})
    assert got["attached"] and got["steps"][0] == {**STEM_OPEN, "target": "SICKO MODE"}, got
    assert "target" not in tools.queue_open_setting({"name": "stem splitter"})["steps"][0]


def test_target_is_refused_on_a_route_without_a_context_menu() -> None:
    got = tools.queue_open_setting({"name": "metronome settings", "target": "Audio 1"})
    assert got["attached"] is False and "takes no target" in got["reason"], got
