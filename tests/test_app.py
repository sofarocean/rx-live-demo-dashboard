"""Smoke tests for app.py.

Runs the Streamlit script headless with streamlit.testing.AppTest and stubs out
the Sofar API with synthetic Rx-LIVE payloads, so the full decode -> map ->
chart -> table path is exercised without network access or an API token.
"""

import logging
import struct
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")
REFERENCE_TAG = "A69-9001-65011"


def encode_payload(records):
    """Encode detections the way the Rx-LIVE sends them: a uint32 LE count
    followed by 11-byte <I H H H c records."""
    out = struct.pack("<I", len(records))
    for serial, freq, channel, count, char in records:
        out += struct.pack("<IHHHc", serial, freq, channel, count, char)
    return out.hex()


FAKE_API_RESPONSE = {
    "data": [
        {
            "timestamp": "2026-10-20T12:00:00.000Z",
            "latitude": 36.80001,
            "longitude": -121.90002,
            "value": encode_payload(
                [
                    (12345, 69, 1602, 3, b"A"),
                    (65011, 69, 9001, 7, b"A"),  # reference tag
                ]
            ),
        },
        {
            "timestamp": "2026-10-28T08:30:00.000Z",
            "latitude": 36.75,
            "longitude": -121.85,
            "value": encode_payload([(54321, 69, 1303, 1, b"A")]),
        },
    ]
}


@pytest.fixture
def mock_api():
    response = mock.Mock(ok=True, text="")
    response.json.return_value = FAKE_API_RESPONSE
    with mock.patch("requests.get", return_value=response) as get:
        yield get


@pytest.fixture
def deprecation_warnings():
    """Collect everything Streamlit logs through its deprecation helper."""
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logger = logging.getLogger("streamlit.deprecation_util")
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)


def fetch(at):
    at.button[0].click().run()
    assert not at.exception, at.exception
    return at


def test_initial_load():
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Bristlemouth Rx-LIVE Acoustic Tag Detections"
    assert at.button[0].label == "Fetch & Decode Data"


def test_fetch_decodes_and_excludes_reference_tag(mock_api):
    at = fetch(AppTest.from_file(APP_PATH, default_timeout=60).run())

    assert mock_api.called
    assert "Found 2 detection(s)." in [m.value for m in at.markdown]

    table = at.dataframe[0].value
    assert list(table["Tag ID"]) == ["A69-1303-54321", "A69-1602-12345"]
    assert list(table["Pings"]) == [1, 3]
    assert REFERENCE_TAG not in set(table["Tag ID"])


def test_fetch_includes_reference_tag_when_not_excluded(mock_api):
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    exclude = next(c for c in at.checkbox if c.label == "Exclude reference tag")
    exclude.uncheck().run()
    at = fetch(at)

    assert "Found 3 detection(s)." in [m.value for m in at.markdown]
    assert REFERENCE_TAG in set(at.dataframe[0].value["Tag ID"])


def test_map_renders_in_iframe(mock_api):
    at = fetch(AppTest.from_file(APP_PATH, default_timeout=60).run())

    iframes = at.get("iframe")
    assert len(iframes) == 1
    html = iframes[0].proto.srcdoc
    assert "leaflet" in html.lower()
    assert html.count("L.marker(") == 2  # one per non-reference detection


def test_chart_resolution_toggle(mock_api):
    at = fetch(AppTest.from_file(APP_PATH, default_timeout=60).run())
    at.radio[0].set_value("1 Week").run()
    assert not at.exception, at.exception


def test_no_streamlit_deprecation_warnings(mock_api, deprecation_warnings):
    # streamlit is unpinned, so this flags newly deprecated APIs in CI before
    # a future release removes them and breaks the deployed app.
    at = fetch(AppTest.from_file(APP_PATH, default_timeout=60).run())
    at.radio[0].set_value("1 Week").run()
    assert not deprecation_warnings, [r.getMessage() for r in deprecation_warnings]
