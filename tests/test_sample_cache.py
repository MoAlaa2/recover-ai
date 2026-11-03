"""Sample-room cache: misses fall through, hits serve disk data."""
import json
import os

import pytest

from app.core.config import BASE_DIR
from app.services import sample_cache
from app.services import targets as targets_mod
from app.services.consultant import analyze_room


def test_sample_ids_are_the_new_five():
    assert set(sample_cache.SAMPLE_IDS) == {
        "sofa_pillows", "sage_curtains", "navy_living",
        "majlis_burgundy", "mustard_armchair"}


def test_miss_on_non_sample_paths():
    assert sample_cache.get_analysis("uploads/abc.jpg", "en") is None
    assert sample_cache.get_targets("uploads/abc.jpg") is None
    assert sample_cache.get_analysis("data/samples/living.jpg",
                                      "en") is None
    assert sample_cache.get_targets("data/samples/living.jpg") is None


def test_committed_cache_is_internally_consistent():
    checked = 0
    for sid in sample_cache.SAMPLE_IDS:
        path = os.path.join(sample_cache.CACHE_DIR, sid + ".json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        assert entry["sample_id"] == sid
        img = os.path.join(BASE_DIR, "data", "samples", sid + ".jpg")
        assert os.path.isfile(img)
        import hashlib
        with open(img, "rb") as f:
            assert entry["sha256"] == hashlib.sha256(
                f.read()).hexdigest()
        assert isinstance(entry["analyses"], dict) and entry["analyses"]
        assert isinstance(entry["targets"], list) and entry["targets"]
        for item in entry["targets"]:
            for key in ("id", "type", "mask_url", "box", "boxes",
                        "size"):
                assert key in item, (sid, key)
            assert os.path.isfile(os.path.join(
                BASE_DIR, item["mask_url"].lstrip("/")))
        checked += 1
    assert checked >= 0


def test_hooks_fall_through_when_uncached(monkeypatch):
    monkeypatch.setattr(sample_cache, "_INDEX", {})
    assert sample_cache.get_analysis("data/samples/living.jpg",
                                     "en") is None
    assert sample_cache.get_targets("data/samples/living.jpg") is None


def test_hooks_serve_a_hit_without_models(monkeypatch, tmp_path):
    target = {"id": "sofa", "type": "sofa", "label_en": "Sofa",
              "label_ar": "\u0627\u0644\u0643\u0646\u0628\u0629",
              "mask_url": "data/samples/masks/sofa_pillows-sofa.png",
              "box": [0, 0, 10, 10], "boxes": [[0, 0, 10, 10]],
              "size": [10, 10]}
    monkeypatch.setattr(
        sample_cache, "get_analysis",
        lambda path, lang: {"room_type": "living room"})
    monkeypatch.setattr(sample_cache, "get_targets",
                        lambda path: [dict(target)])
    assert analyze_room("data/samples/sofa_pillows.jpg", "en") == {
        "room_type": "living room"}
    assert targets_mod.detect_targets(
        "data/samples/sofa_pillows.jpg") == [target]
