"""Multi-item swap tests (model calls are faked)."""
import io
import json
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import swap as s


TMP = "/tmp/recover-swapmulti-test"


def setup_function(_):
    os.makedirs(TMP, exist_ok=True)


def solid(color, size=(64, 48)):
    return Image.new("RGB", size, color)


def make_room(tmp_path):
    room = tmp_path / "room.jpg"
    solid((10, 20, 30)).save(str(room))
    return str(room)


@pytest.fixture
def fakes(monkeypatch):
    calls = {"segment": [], "edit": [], "verify": 0}

    def fake_segment(room_bytes, concept, key=None):
        calls["segment"].append(concept)
        if concept == "sofa":
            return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]
        return [{"box": (10, 10, 30, 30), "frame_size": (100, 100)}]

    def fake_mask(records, size):
        return Image.new("L", size, 255)

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None):
        calls["edit"].append(concept)
        shade = 100 if concept == "sofa" else 180
        return solid((shade, shade, shade))

    def fake_verify(swatch_bytes, result, fabric, concept, key=None):
        calls["verify"] += 1
        return {"color": 8, "pattern": 8, "scale": 8, "isolation": 8}

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", fake_mask)
    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify", fake_verify)
    return calls


def test_multi_largest_first_and_files(tmp_path, fakes):
    room = make_room(tmp_path)
    out = tmp_path / "out"
    res = s.swap_multi(room, [{"target": "cushions", "code": "FA-AC-02"},
                              {"target": "sofa", "code": "FA-AC-01"}],
                       api_key="k", out_dir=str(out))
    assert fakes["edit"] == ["sofa", "cushions"]
    assert [r["target"] for r in res["results"]] == ["sofa", "cushions"]
    assert all(r["attempts"] == 1 and r["cached"] is False
               for r in res["results"])
    for r in res["results"]:
        assert os.path.exists(os.path.join(str(out), os.path.basename(
            r["result_url"])))
    assert os.path.exists(os.path.join(
        str(out), os.path.basename(res["final_url"])))


def test_multi_cache_reuses_without_calls(tmp_path, fakes):
    room = make_room(tmp_path)
    out = tmp_path / "out"
    first = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                         api_key="k", out_dir=str(out))
    assert first["results"][0]["cached"] is False
    fakes["segment"].clear()
    fakes["edit"].clear()
    second = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                          api_key="k", out_dir=str(out))
    assert second["results"][0]["cached"] is True
    assert fakes["segment"] == [] and fakes["edit"] == []


def test_multi_retry_once_on_low_scores(tmp_path, monkeypatch):
    room = make_room(tmp_path)
    scores = [{"color": 5, "pattern": 8, "scale": 8, "isolation": 8},
              {"color": 8, "pattern": 8, "scale": 8, "isolation": 8}]
    edits = []

    def fake_segment(room_bytes, concept, key=None):
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: edits.append(1) or solid((9, 9, 9)))
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: scores[min(len(edits) - 1, 1)])
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                       api_key="k", out_dir=str(tmp_path / "o"))
    assert res["results"][0]["attempts"] == 2
    assert len(edits) == 2
    assert res["results"][0]["scores"]["color"] == 8


def test_multi_skips_failed_item_keeps_rest(tmp_path, monkeypatch):
    room = make_room(tmp_path)

    def fake_segment(room_bytes, concept, key=None):
        if concept == "cushions":
            return []
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: solid((9, 9, 9)))
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: {"color": 8, "pattern": 8,
                                         "scale": 8, "isolation": 8})
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"},
                              {"target": "cushions",
                               "code": "FA-AC-02"}],
                       api_key="k", out_dir=str(tmp_path / "o"))
    assert [r["target"] for r in res["results"]] == ["sofa"]
    assert res["skipped"][0]["target"] == "cushions"
    assert "could not find" in res["skipped"][0]["reason"]
    assert os.path.exists(os.path.join(
        str(tmp_path / "o"), os.path.basename(res["final_url"])))


def test_multi_skips_edit_failure(tmp_path, monkeypatch):
    room = make_room(tmp_path)

    def fake_segment(room_bytes, concept, key=None):
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None):
        if concept == "cushions":
            raise s.SwapError("fabric edit failed: boom")
        return solid((9, 9, 9))

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: {"color": 8, "pattern": 8,
                                         "scale": 8, "isolation": 8})
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"},
                              {"target": "cushions",
                               "code": "FA-AC-02"}],
                       api_key="k", out_dir=str(tmp_path / "o"))
    assert [r["target"] for r in res["results"]] == ["sofa"]
    assert res["skipped"][0]["code"] == "FA-AC-02"


def test_multi_all_fail_still_raises(tmp_path, monkeypatch):
    room = make_room(tmp_path)
    monkeypatch.setattr(s, "segment", lambda *a, **k: [])
    res_before = None
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                     api_key="k", out_dir=str(tmp_path / "o"))
    assert res_before is None


def test_multi_rejects_bad_input(tmp_path):
    room = make_room(tmp_path)
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [], api_key="k",
                     out_dir=str(tmp_path / "o"))
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [{"target": "lamp", "code": "FA-AC-01"}],
                     api_key="k", out_dir=str(tmp_path / "o"))
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [{"target": "sofa", "code": "NOPE"}],
                     api_key="k", out_dir=str(tmp_path / "o"))


def test_multi_endpoint_shape(monkeypatch, tmp_path):
    from app.main import app
    room = make_room(tmp_path)
    rel = os.path.relpath(room, os.getcwd() + "/recover-ai") \
        if room.startswith(os.getcwd()) else room

    def fake_multi(room_path, assignments, **kwargs):
        return {"results": [{"target": a["target"], "code": a["code"],
                             "result_url": "uploads/swap/r.jpg",
                             "mask_url": "uploads/swap/m.png",
                             "scores": {"color": 8}, "attempts": 1,
                             "cached": False} for a in assignments],
                "final_url": "uploads/swap/final.jpg"}

    monkeypatch.setattr("app.services.swap.swap_multi", fake_multi)
    client = TestClient(app)
    resp = client.post(
        "/api/swap/multi",
        json={"session_id": "t-multi", "image_path": room,
              "assignments": [{"target": "sofa", "code": "FA-AC-01"}]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["final_url"].endswith("final.jpg")
    assert body["results"][0]["target"] == "sofa"


def test_multi_endpoint_rejects(monkeypatch, tmp_path):
    from app.main import app
    room = make_room(tmp_path)
    client = TestClient(app)
    bad_target = client.post(
        "/api/swap/multi",
        json={"session_id": "t-m", "image_path": room,
              "assignments": [{"target": "lamp", "code": "FA-AC-01"}]})
    assert bad_target.status_code == 400
    bad_code = client.post(
        "/api/swap/multi",
        json={"session_id": "t-m", "image_path": room,
              "assignments": [{"target": "sofa", "code": "NOPE"}]})
    assert bad_code.status_code == 400
    missing = client.post(
        "/api/swap/multi",
        json={"session_id": "t-m", "image_path": "uploads/nope.jpg",
              "assignments": [{"target": "sofa", "code": "FA-AC-01"}]})
    assert missing.status_code == 400


def test_fabrics_browse_filters():
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/fabrics",
                      params={"suitable_for": "curtains",
                              "usage": "curtains", "limit": 5})
    assert resp.status_code == 200
    fabrics = resp.json()["fabrics"]
    assert 1 <= len(fabrics) <= 5
    assert all("code" in f and "price_sar_per_m" in f for f in fabrics)


def test_assignments_roundtrip():
    from app.main import app
    client = TestClient(app)
    put = client.post("/api/session/t-asg/assignments",
                      json={"target": "sofa", "code": "FA-AC-01"})
    assert put.status_code == 200
    assert put.json()["assignments"] == {"sofa": "FA-AC-01"}
    bad = client.post("/api/session/t-asg/assignments",
                      json={"target": "lamp", "code": "FA-AC-01"})
    assert bad.status_code == 400
    wipe = client.delete("/api/session/t-asg/assignments")
    assert wipe.status_code == 200
    assert wipe.json() == {"assignments": {}}
