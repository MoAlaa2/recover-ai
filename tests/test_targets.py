"""Multi-object target detection (model calls are faked)."""
import json

from PIL import Image
from fastapi.testclient import TestClient

from app.services import targets as t


def vision(items):
    def fake(messages):
        return {"choices": [{"message": {"content": json.dumps(
            {"items": items})}}]}
    return fake


def test_list_types_keeps_known_types(monkeypatch):
    monkeypatch.setattr(t, "_call_vision",
                        vision(["sofa", "bed", "curtains"]))
    assert t.list_types("data/samples/living.jpg") == ["sofa", "curtains"]


def test_list_types_downscales_vision(monkeypatch):
    import base64
    import io as _io
    seen = {}

    def fake(messages):
        url = messages[0]["content"][1]["image_url"]["url"]
        seen["b64"] = url.split(",", 1)[1]
        return {"choices": [{"message": {"content": '{"items": []}'}}]}

    monkeypatch.setattr(t, "_call_vision", fake)
    assert t.list_types("data/samples/living.jpg") == []
    im = Image.open(_io.BytesIO(base64.b64decode(seen["b64"])))
    assert max(im.size) <= 1024


def test_list_types_empty_on_garbage(monkeypatch):
    monkeypatch.setattr(t, "_call_vision", lambda m: {
        "choices": [{"message": {"content": "no json here"}}]})
    assert t.list_types("data/samples/living.jpg") == []


def test_masks_subtract_cushions_from_sofa(monkeypatch, tmp_path):
    room = tmp_path / "room.jpg"
    Image.new("RGB", (40, 30), (200, 180, 160)).save(str(room))
    monkeypatch.setattr(t, "require_api_key", lambda: "k")
    monkeypatch.setattr(t, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(t, "list_types", lambda path: ["sofa", "cushions"])
    # Shared listing cache: identical image bytes across tests must not
    # leak one test's listing into another.
    t.TARGETS_CACHE.clear()

    def fake_segment(room_bytes, concept, key):
        return [{"concept": concept}]

    def fake_sam(records, size):
        if "cushion" in records[0]["concept"] \
                or "pillow" in records[0]["concept"]:
            mask = Image.new("L", size, 0)
            for x in range(10, 20):
                for y in range(10, 20):
                    mask.putpixel((x, y), 255)
            return mask
        return Image.new("L", size, 255)

    monkeypatch.setattr(t, "segment", fake_segment)
    monkeypatch.setattr(t, "sam_mask", fake_sam)
    out = t.detect_targets(str(room))
    by_id = {item["id"]: item for item in out}
    assert set(by_id) == {"sofa", "cushions"}
    assert by_id["sofa"]["box"] == [0, 0, 40, 30]
    assert by_id["cushions"]["box"] == [10, 10, 20, 20]
    # Two items compete: the full-photo sofa blob cannot disambiguate,
    # so it is not a tap; the tight cushions blob stays.
    assert by_id["sofa"]["boxes"] == []
    assert by_id["cushions"]["boxes"] == [[10, 10, 20, 20]]
    assert by_id["sofa"]["label_ar"] == "الكنبة"
    # Room pixel size rides along so the chat can place % taps.
    assert by_id["sofa"]["size"] == [40, 30]
    assert by_id["cushions"]["size"] == [40, 30]
    sofa_mask = Image.open(
        str(tmp_path / "masks" / by_id["sofa"]["mask_url"].split(
            "masks/")[1]))
    # Cushion area was subtracted from the sofa mask.
    assert sofa_mask.getpixel((15, 15)) == 0
    assert sofa_mask.getpixel((0, 0)) == 255


def test_masks_fall_back_to_raw_concept(monkeypatch, tmp_path):
    room = tmp_path / "room.jpg"
    Image.new("RGB", (40, 30), (200, 180, 160)).save(str(room))
    monkeypatch.setattr(t, "require_api_key", lambda: "k")
    monkeypatch.setattr(t, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(t, "list_types", lambda path: ["cushions"])
    t.TARGETS_CACHE.clear()
    calls = []

    def fake_segment(room_bytes, concept, key):
        calls.append(concept)
        if concept == "cushions":
            return [{"concept": concept}]
        return []

    monkeypatch.setattr(t, "segment", fake_segment)
    monkeypatch.setattr(
        t, "sam_mask", lambda records, size: Image.new("L", size, 255))
    by_id = {item["id"]: item
             for item in t.detect_targets(str(room))}
    assert set(by_id) == {"cushions"}
    assert calls == ["throw pillows on the sofa", "cushions"]


def test_lone_item_keeps_closeup_tap(monkeypatch, tmp_path):
    room = tmp_path / "room.jpg"
    Image.new("RGB", (40, 30), (200, 180, 160)).save(str(room))
    monkeypatch.setattr(t, "require_api_key", lambda: "k")
    monkeypatch.setattr(t, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(t, "list_types", lambda path: ["sofa"])
    t.TARGETS_CACHE.clear()
    monkeypatch.setattr(t, "segment",
                        lambda rb, concept, key: [{"concept": concept}])
    monkeypatch.setattr(
        t, "sam_mask", lambda records, size: Image.new("L", size, 255))
    by_id = {item["id"]: item
             for item in t.detect_targets(str(room))}
    assert by_id["sofa"]["boxes"] == [[0, 0, 40, 30]]


def test_component_boxes_ignore_specks():
    from PIL import Image
    mask = Image.new("L", (100, 80), 0)
    for x in range(20, 60):
        for y in range(20, 50):
            mask.putpixel((x, y), 255)
    for x in range(70, 90):
        for y in range(60, 75):
            mask.putpixel((x, y), 255)
    mask.putpixel((0, 0), 255)
    mask.putpixel((99, 79), 255)
    boxes = t._component_boxes(mask)
    assert boxes == [[20, 20, 60, 50], [70, 60, 90, 75]]


def test_targets_endpoint_caches_per_session(monkeypatch):
    from app.main import app
    from app.services import consultant
    seen = {"n": 0}

    def fake_detect(image_path):
        seen["n"] += 1
        return [{"id": "sofa", "type": "sofa", "label_en": "Sofa",
                 "label_ar": "الكنبة",
                 "mask_url": "uploads/masks/m.png", "box": [0, 0, 8, 8]}]

    monkeypatch.setattr("app.api.chat.targets_mod.detect_targets",
                        fake_detect)
    client = TestClient(app)
    first = client.get("/api/session/t-sess-1/targets",
                       params={"image_path": "data/samples/living.jpg"})
    assert first.status_code == 200
    assert [x["id"] for x in first.json()["targets"]] == ["sofa"]
    second = client.get("/api/session/t-sess-1/targets",
                        params={"image_path": "data/samples/living.jpg"})
    assert second.status_code == 200
    assert seen["n"] == 1
    consultant.SESSIONS.pop("t-sess-1", None)


def test_targets_endpoint_missing_image():
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/session/t-sess-2/targets",
                      params={"image_path": "uploads/nope.jpg"})
    assert resp.status_code == 400


def test_available_types_calls_through(tmp_path, monkeypatch):
    from PIL import Image as PILImage
    room = tmp_path / "room.jpg"
    PILImage.new("RGB", (32, 24), (1, 2, 3)).save(str(room))
    monkeypatch.setattr(t, "list_types", lambda image_path: ["sofa"])
    t.TARGETS_CACHE.clear()
    assert t.available_types(str(room)) == ["sofa"]
    assert t.available_types(str(room)) == ["sofa"]


def test_match_targets_choice_words():
    avail = ["sofa", "cushions", "curtains"]
    assert t.match_targets("the curtains please", avail) == (
        ["curtains"], {})
    assert t.match_targets("الكنبة", avail) == (["sofa"], {})
    assert t.match_targets("all of them", avail) == (avail, {"all": True})
    chosen, flags = t.match_targets("just show me", avail)
    assert chosen == avail and flags == {"skip": True}
    assert t.match_targets("something else", avail) == ([], {})
    assert t.match_targets("sofa and curtains", avail) == (
        ["sofa", "curtains"], {})


def test_count_components_blobs_and_noise(tmp_path):
    from PIL import Image, ImageDraw
    img = Image.new("L", (200, 200), 0)
    draw = ImageDraw.Draw(img)
    draw.ellipse([10, 10, 60, 60], fill=255)
    draw.ellipse([80, 20, 140, 70], fill=255)
    draw.rectangle([20, 100, 90, 170], fill=255)
    draw.point((150, 150), fill=255)
    path = str(tmp_path / "mask.png")
    img.save(path)
    assert t.count_components(path) == 3
    assert t.count_components(Image.new("L", (100, 100), 0)) == 0


def test_subtract_cushions_keeps_sofa_when_erased():
    from PIL import Image
    from app.services import targets as tmod
    sofa = Image.new("L", (100, 100), 255)
    cush = Image.new("L", (100, 100), 255)
    assert tmod._subtract_cushions(sofa, cush) is sofa


def test_match_targets_five_languages():
    from app.services import targets as tmod
    avail = ["sofa", "cushions", "curtains"]
    # "All" in hi/fr/es must open the multi flow like en/ar do.
    assert tmod.match_targets("Tout", avail) == (avail, {"all": True})
    assert tmod.match_targets("todos", avail) == (avail, {"all": True})
    assert tmod.match_targets("सभी", avail) == (avail, {"all": True})
    assert tmod.match_targets("सब कुछ बदलो", avail) == (
        avail, {"all": True})
    # Items in hi/fr/es.
    assert tmod.match_targets("le canapé", avail) == (["sofa"], {})
    assert tmod.match_targets("fauteuil", avail) == (["sofa"], {})
    assert tmod.match_targets("les coussins", avail) == (
        ["cushions"], {})
    assert tmod.match_targets("los cojines", avail) == (["cushions"], {})
    assert tmod.match_targets("las cortinas", avail) == (
        ["curtains"], {})
    assert tmod.match_targets("les rideaux", avail) == (["curtains"], {})
    assert tmod.match_targets("परदे", avail) == (["curtains"], {})
    # Bare सब is a substring of सबसे/सबूत: never an "all" match.
    assert tmod.match_targets("सबसे अच्छा कपड़ा", avail) == ([], {})
    assert tmod.match_targets("blabla", avail) == ([], {})


def test_subtract_cushions_normal_case():
    from PIL import Image, ImageDraw
    from app.services import targets as tmod
    sofa = Image.new("L", (100, 100), 255)
    cush = Image.new("L", (100, 100), 0)
    ImageDraw.Draw(cush).rectangle([10, 10, 30, 30], fill=255)
    out = tmod._subtract_cushions(sofa, cush)
    assert out is not sofa
    assert out.getpixel((20, 20)) == 0
    assert out.getpixel((80, 80)) == 255


def test_list_types_reports_armchair(monkeypatch):
    # An armchair photo (the showroom sample) has no sofa: Spark names
    # the chair and it becomes its own target.
    monkeypatch.setattr(t, "_call_vision",
                        vision(["chair", "cushions", "curtains"]))
    assert t.list_types("data/samples/armchair.jpg") == [
        "armchair", "cushions", "curtains"]
    monkeypatch.setattr(t, "_call_vision", vision(["sofa", "armchair"]))
    assert t.list_types("data/samples/living.jpg") == ["sofa", "armchair"]


def test_match_targets_armchair_words():
    avail = ["armchair", "cushions", "curtains"]
    assert t.match_targets("the armchair", avail) == (["armchair"], {})
    assert t.match_targets("الكرسي", avail) == (["armchair"], {})
    assert t.match_targets("le fauteuil", avail) == (["armchair"], {})
    # Both seats listed: chair words pick the chair only.
    both = ["sofa", "armchair", "cushions"]
    assert t.match_targets("sillón", both) == (["armchair"], {})
    assert t.match_targets("sofa", both) == (["sofa"], {})
    # No armchair in the photo: chair words still land on the sofa.
    assert t.match_targets("the chair", ["sofa", "curtains"]) == (
        ["sofa"], {})


def test_masks_subtract_cushions_from_armchair(monkeypatch, tmp_path):
    from PIL import Image, ImageDraw
    room = tmp_path / "chair.jpg"
    Image.new("RGB", (100, 100), (120, 110, 100)).save(str(room))
    calls = []

    def fake_segment(room_bytes, concept, key):
        calls.append(concept)
        return [{"concept": concept}]

    def fake_mask(records, size):
        m = Image.new("L", size, 0)
        d = ImageDraw.Draw(m)
        if records[0]["concept"] == "armchair":
            d.rectangle([10, 10, 60, 60], fill=255)
        else:
            d.rectangle([20, 20, 30, 30], fill=255)
        return m

    monkeypatch.setattr(t, "segment", fake_segment)
    monkeypatch.setattr(t, "sam_mask", fake_mask)
    monkeypatch.setattr(t, "require_api_key", lambda: "k")
    masks = t.masks_for(str(room), ["armchair", "cushions"])
    assert "armchair" in calls
    assert masks["armchair"].getpixel((25, 25)) == 0  # cushion cut out
    assert masks["armchair"].getpixel((50, 50)) == 255
