from __future__ import annotations

import gzip
import json

import pytest

from app.analytics.store import (
    DatasetError,
    analysis_from_payload,
    build_payload,
    load_payload,
    save_payload,
)
from app.analytics.cutoff import CutoffPolicy


def test_payload_roundtrip_preserves_provenance(leakage_service, tmp_path):
    payload = build_payload(
        leakage_service.analysis,
        actual_fetch={"records_received": 48},
        forecast_fetch={"records_received": 48},
        is_test_data=True,
    )
    path = tmp_path / "dataset.json.gz"
    save_payload(payload, path)
    loaded = load_payload(path)
    assert loaded["is_test_data"] is True
    assert loaded["scope"]["start"] == "2026-01-01"
    assert loaded["scope"]["end"] == "2026-01-31"
    assert loaded["fetch"]["actual"]["records_received"] == 48
    assert len(loaded["actuals"]) == 48
    assert len(loaded["forecasts"]) == 48


def test_loaded_payload_rebuilds_identical_metrics(leakage_service, tmp_path):
    payload = build_payload(
        leakage_service.analysis,
        actual_fetch={},
        forecast_fetch={},
        is_test_data=True,
    )
    path = tmp_path / "dataset.json.gz"
    save_payload(payload, path)
    loaded = load_payload(path)
    analysis = analysis_from_payload(
        loaded, policy=CutoffPolicy(), mape_min_actual_mw=100.0
    )
    assert analysis.summary()["mae_mw"] == 200.0
    assert analysis.test_data is True


def test_missing_file_raises_actionable_error(tmp_path):
    with pytest.raises(DatasetError, match="python -m app.data.refresh"):
        load_payload(tmp_path / "absent.json.gz")


def test_wrong_scope_is_refused(tmp_path):
    payload = {
        "schema_version": 1,
        "scope": {"start": "2025-12-01", "end": "2025-12-31"},
        "actuals": [],
        "forecasts": [],
    }
    path = tmp_path / "wrong.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    with pytest.raises(DatasetError, match="scope"):
        load_payload(path)


def test_wrong_schema_version_is_refused(tmp_path):
    payload = {
        "schema_version": 999,
        "scope": {"start": "2026-01-01", "end": "2026-01-31"},
        "actuals": [],
        "forecasts": [],
    }
    path = tmp_path / "old.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    with pytest.raises(DatasetError, match="schema version"):
        load_payload(path)


def test_corrupt_gzip_is_refused(tmp_path):
    path = tmp_path / "corrupt.json.gz"
    path.write_bytes(b"not actually gzip")
    with pytest.raises(DatasetError, match="could not be read"):
        load_payload(path)


def test_non_object_payload_is_refused(tmp_path):
    path = tmp_path / "list.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump([1, 2, 3], handle)
    with pytest.raises(DatasetError, match="not a JSON object"):
        load_payload(path)


def test_missing_data_arrays_are_refused(tmp_path):
    payload = {
        "schema_version": 1,
        "scope": {"start": "2026-01-01", "end": "2026-01-31"},
        "actuals": [],
    }
    path = tmp_path / "incomplete.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    with pytest.raises(DatasetError, match="forecasts"):
        load_payload(path)
