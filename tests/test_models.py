"""Model profiles and status names (H14 Pro, H15 Mix, H15 Pro Heat, unknown)."""
import logging

import pytest
from homeassistant.const import Platform

from custom_components.dreame_wet_dry_vacuum.const import (
    DEVICE_STATUS,
    H14_PRO_MODEL,
    H15_MIX_MODEL,
    H15_PRO_HEAT_MODEL,
    H15_PRO_HEAT_MODEL_ALT,
    H15_PRO_MODEL,
)
from custom_components.dreame_wet_dry_vacuum.models import (
    GENERIC,
    H14_PRO,
    H15_MIX,
    H15_PRO,
    H15_PRO_HEAT,
    describe_status,
    get_profile,
    status_code,
    status_group,
)

UNKNOWN_MODEL = "dreame.hold.w9999z"


def _records(caplog, text: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if text in r.getMessage()]


class TestProfiles:
    @pytest.mark.parametrize(
        ("model", "profile"),
        [
            (H14_PRO_MODEL, H14_PRO),
            (H15_MIX_MODEL, H15_MIX),
            (H15_PRO_HEAT_MODEL, H15_PRO_HEAT),
            (H15_PRO_HEAT_MODEL_ALT, H15_PRO_HEAT),
            (H15_PRO_MODEL, H15_PRO),
            (UNKNOWN_MODEL, GENERIC),
            ("", GENERIC),
            (None, GENERIC),
        ],
    )
    def test_model_picks_profile(self, model, profile):
        assert get_profile(model) is profile

    def test_untested_profiles_send_no_commands(self):
        for profile in (H15_PRO_HEAT, GENERIC):
            assert profile.tested is False
            assert profile.button_keys == frozenset()
            assert set(profile.platforms) == {Platform.SENSOR, Platform.BINARY_SENSOR}

    def test_tested_profiles_keep_their_platforms(self):
        assert H14_PRO.tested and H15_MIX.tested
        assert Platform.SWITCH in H14_PRO.platforms
        assert set(H15_MIX.platforms) == {
            Platform.SENSOR,
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
        }

    def test_untested_model_logged_once_without_account_data(self, caplog):
        caplog.set_level(logging.INFO)
        get_profile(UNKNOWN_MODEL)
        get_profile(UNKNOWN_MODEL)
        records = _records(caplog, UNKNOWN_MODEL)
        assert len(records) == 1
        assert records[0].levelno == logging.INFO

    def test_tested_model_not_logged(self, caplog):
        caplog.set_level(logging.DEBUG)
        get_profile(H14_PRO_MODEL)
        assert _records(caplog, H14_PRO_MODEL) == []


class TestStatusCode:
    @pytest.mark.parametrize(
        ("raw", "code"),
        [(7, 7), ("7", 7), ([26], 26), ([], None), (None, None), (True, None),
         ("abc", None), ({"x": 1}, None)],
    )
    def test_status_code(self, raw, code):
        assert status_code(raw) == code


class TestStatusNames:
    def test_h14_pro_uses_its_table(self):
        assert describe_status(H14_PRO, H14_PRO_MODEL, 7) == DEVICE_STATUS[7]
        assert status_group(H14_PRO, 4) == "charging"

    def test_h15_mix_english_and_german(self):
        assert describe_status(H15_MIX, H15_MIX_MODEL, 26, "en") == "Hot-water self-cleaning"
        assert describe_status(H15_MIX, H15_MIX_MODEL, 26, "de-CH") == (
            "Heißwasser-Selbstreinigung"
        )
        # A language without its own table falls back to English.
        assert describe_status(H15_MIX, H15_MIX_MODEL, 4, "fr") == "Charging"

    def test_h15_pro_heat_codes_from_captures(self):
        assert describe_status(H15_PRO_HEAT, H15_PRO_HEAT_MODEL, 42) == (
            "Hot water self-cleaning"
        )
        assert status_group(H15_PRO_HEAT, 42) == "self_cleaning"
        assert status_group(H15_PRO_HEAT, 33) == "drying"

    def test_unknown_model_reads_generic_names(self):
        assert describe_status(GENERIC, UNKNOWN_MODEL, 4) == "Charging"
        assert status_group(GENERIC, 4) == "charging"

    def test_unknown_code_reads_status_n_and_logs_once(self, caplog):
        caplog.set_level(logging.INFO)
        assert describe_status(GENERIC, UNKNOWN_MODEL, 77) == "Status 77"
        assert describe_status(GENERIC, UNKNOWN_MODEL, [77]) == "Status 77"
        assert status_group(GENERIC, 77) == "unknown"
        records = _records(caplog, "status 77")
        assert len(records) == 1
        assert UNKNOWN_MODEL in records[0].getMessage()

    def test_each_new_code_is_logged(self, caplog):
        caplog.set_level(logging.INFO)
        describe_status(GENERIC, UNKNOWN_MODEL, 77)
        describe_status(GENERIC, UNKNOWN_MODEL, 78)
        assert len(_records(caplog, "status 7")) == 2

    def test_known_code_not_logged(self, caplog):
        caplog.set_level(logging.DEBUG)
        describe_status(H14_PRO, H14_PRO_MODEL, 7)
        assert _records(caplog, "does not know") == []

    def test_missing_or_odd_values(self):
        assert describe_status(GENERIC, UNKNOWN_MODEL, None) is None
        assert describe_status(GENERIC, UNKNOWN_MODEL, "abc") == "abc"
        assert status_group(GENERIC, None) is None
        assert status_group(GENERIC, "abc") is None


class TestH15Pro:
    """H15 Pro (w2448e): values captured over MQTT on 2026-11-16."""

    def test_own_control_tables(self):
        assert H15_PRO.selects[(16, 1)]["options"] == {1: "light", 2: "standard", 3: "strong"}
        assert H15_PRO.selects[(16, 2)]["options"][3] == "wet"
        assert H15_PRO.selects[(200, 3)]["options"] == {
            16384: "standard", 20480: "deep", 24576: "auto",
        }
        assert H15_PRO.selects[(1, 10)]["options"] == {3: "turbo_5min", 1: "high_30min"}
        assert (16, 6) in H15_PRO.switches and (1, 7) in H15_PRO.switches
        assert (1, 3) not in H15_PRO.switches  # no light on this model
        assert (23, 1) not in H15_PRO.selects  # rejected by the device
        # Only codes captured on the H15 Pro itself.
        assert set(H15_PRO.switches) == {(16, 6), (1, 7)}
        assert set(H15_PRO.selects) == {(16, 1), (16, 2), (200, 3), (1, 10)}
        assert not H15_PRO.numbers and not H15_PRO.button_keys

    def test_h14_profile_keeps_global_tables(self):
        assert H14_PRO.switches is None and H14_PRO.selects is None
