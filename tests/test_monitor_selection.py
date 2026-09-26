"""Tests for single-monitor capture (config.MONITOR_INDEX / --monitor)."""

from types import SimpleNamespace

import pytest

from openadapt_capture import recorder, utils
from openadapt_capture.config import RecordingConfig, config, config_override

# mss layout: [0] = virtual desktop, [1] = primary, [2] = secondary (left of primary)
FAKE_MONITORS = [
    {"left": -1920, "top": 0, "width": 3840, "height": 1080},
    {"left": 0, "top": 0, "width": 1920, "height": 1080},
    {"left": -1920, "top": 0, "width": 1920, "height": 1080},
]


@pytest.fixture
def fake_monitors(monkeypatch):
    monkeypatch.setattr(
        utils, "get_process_local_sct", lambda: SimpleNamespace(monitors=FAKE_MONITORS)
    )


class TestMonitorInfo:
    """Tests for utils monitor helpers."""

    def test_list_monitors(self, fake_monitors):
        assert utils.list_monitors() == FAKE_MONITORS

    def test_get_monitor_info_explicit_index(self, fake_monitors):
        assert utils.get_monitor_info(2) == FAKE_MONITORS[2]

    def test_get_monitor_info_defaults_to_config(self, fake_monitors):
        with config_override(RecordingConfig(monitor_index=1)):
            assert utils.get_monitor_info() == FAKE_MONITORS[1]
        assert utils.get_monitor_info() == FAKE_MONITORS[config.MONITOR_INDEX]

    @pytest.mark.parametrize("index", [-1, 3, 99])
    def test_get_monitor_info_out_of_range_falls_back_to_all(self, fake_monitors, index):
        assert utils.get_monitor_info(index) == FAKE_MONITORS[0]

    def test_get_monitor_dims(self, fake_monitors):
        assert utils.get_monitor_dims(0) == (3840, 1080)
        assert utils.get_monitor_dims(1) == (1920, 1080)


class TestTranslateCoords:
    """Tests for recorder._translate_coords."""

    def test_all_monitors_passes_through(self):
        assert recorder._translate_coords(-500, 300, None) == (-500, 300)

    def test_inside_monitor_is_made_relative(self):
        assert recorder._translate_coords(-1900, 50, FAKE_MONITORS[2]) == (20, 50)

    def test_top_left_corner_maps_to_origin(self):
        assert recorder._translate_coords(-1920, 0, FAKE_MONITORS[2]) == (0, 0)

    @pytest.mark.parametrize("x,y", [(0, 0), (500, 500), (-1920, 1080), (-1921, 0)])
    def test_outside_monitor_is_dropped(self, x, y):
        assert recorder._translate_coords(x, y, FAKE_MONITORS[2]) is None


class TestMouseHandlers:
    """Mouse handlers filter and translate events for the selected monitor."""

    @pytest.fixture
    def captured(self, monkeypatch):
        events = []
        monkeypatch.setattr(
            recorder, "trigger_action_event", lambda q, args: events.append(args)
        )
        return events

    def test_on_move_translates(self, captured):
        recorder.on_move(None, 100, 200, monitor_bounds=FAKE_MONITORS[2])
        assert captured == []
        recorder.on_move(None, -1820, 200, monitor_bounds=FAKE_MONITORS[2])
        assert captured == [{"name": "move", "mouse_x": 100, "mouse_y": 200}]

    def test_on_click_outside_monitor_dropped(self, captured):
        recorder.on_click(
            None, 100, 200, recorder.mouse.Button.left, True,
            monitor_bounds=FAKE_MONITORS[2],
        )
        assert captured == []

    def test_on_scroll_translates(self, captured):
        recorder.on_scroll(None, 110, 20, 0, -1, monitor_bounds=FAKE_MONITORS[1])
        assert captured[0]["mouse_x"] == 110
        assert captured[0]["mouse_y"] == 20

    def test_no_bounds_keeps_absolute_coords(self, captured):
        recorder.on_move(None, -1820, 200)
        assert captured == [{"name": "move", "mouse_x": -1820, "mouse_y": 200}]
