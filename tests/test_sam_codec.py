"""SAM 3.1 mask codec tests (offline; uses a recorded one_bit response)."""
import pytest

from app.services import sam_codec as m

# Recorded live response for concept "sofa" on a 1600x1600 room photo
# (mask 382 rows x 1024 cols, one_bit). Payload complete and unmodified.
FIXTURE = ("<0f>0<|box;x1=197;y1=830;x2=1361;y2=1264;w=1600;h=1600|>"
           "<|mask;x=0;y=0;data=382,1024,!!!!&y?l%?gH%Ds?J1^dpTw/`PG75W+N*-!te=1J8W_*eJTAACgq1U'XpaN-eTG*=W7M1m_W5(FI:&bA(YvlN&7Yta]HE#jAQbpsGGvU=0(?m31DY^TSvN7VU3K@Hd/M.K`V*6fOJC`_-c4&Q%8.l(LJhHAnc&//swk2zW?*Wr)/9so#n54mY03+JZ?tqTzoTRqf(!12Q**7'.JqF/C..n[2]2)q2obNG{Xe!V'%/QdnlA#WMGNmOJ=GssAcF%q7Ry68ToJ(WjTZ/2QBAZh4pM`8Tj+63X+?Ce9o!l)8b&Mh$!qevw`Gy%t#RtlNoL6uJZFKJK88mt5TY1RcbXyL741Jz9AH0y63G7C[.:LE&W]qTE'2v[?Svg{%AIgSa5WDQ5CGW2?`wc60Px5V#/:fNErY[SU@0u'=QA_P7Nw/hROY=sH&8gywnSHhrXzKMg[)rqWqBcq/A@jYxrCRkGh2PyzETBeMYv*POIPqcwg]YD#A[Oq4Zy1)x4koAg8il9h5w/fjohCPaY-{H8+8Q1gmFn|>")


def test_parse_record_fields():
    recs = m.parse_output_text(FIXTURE)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["id"] == 0
    assert rec["frame"] == 0
    assert rec["box"] == (197, 830, 1361, 1264)
    assert rec["frame_size"] == (1600, 1600)
    assert rec["mask_size"] == (382, 1024)
    assert rec["mask_encoding"] == "one_bit"
    assert rec["mask_payload"].startswith("!")


def test_parse_empty_and_garbage():
    assert m.parse_output_text("") == []
    assert m.parse_output_text("no masks here") == []
    assert m.parse_output_text("<0f>") == []


def test_decode_one_bit_shape_and_binary():
    recs = m.parse_output_text(FIXTURE)
    raster, width, height = m.decode_record(recs[0])
    assert (width, height) == (1024, 382)
    assert len(raster) == width * height
    assert set(raster) <= {0, 1}
    assert sum(raster) == 258061


def test_decode_rejects_lossless():
    rec = {"mask_encoding": "lossless", "mask_payload": "~abc",
           "mask_size": (2, 2)}
    with pytest.raises(m.MaskError):
        m.decode_record(rec)


def test_unpack_rejects_bad_length():
    with pytest.raises(m.MaskError):
        m.unpack("!!!!!" + "A")
    with pytest.raises(m.MaskError):
        m.unpack("!!")


def test_unpack_rejects_bad_characters():
    with pytest.raises(m.MaskError):
        m.unpack("!!!!,")
