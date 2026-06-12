from types import SimpleNamespace

from app.hatch_signature import effective_pattern_angle, hatch_signature, signature_key


def test_effective_pattern_angle_uses_pattern_lines():
    hatch = SimpleNamespace(
        dxf=SimpleNamespace(pattern_angle=0, pattern_name="ANSI31", solid_fill=0, pattern_scale=1.0),
        pattern=SimpleNamespace(lines=[SimpleNamespace(angle=90)]),
    )
    assert effective_pattern_angle(hatch) == 90.0


def test_hatch_signature_includes_pattern_and_angle_bucket():
    hatch = SimpleNamespace(
        dxf=SimpleNamespace(pattern_angle=45, pattern_name="ANSI31", solid_fill=0, pattern_scale=2.0, color=1, layer="HATCH"),
        pattern=SimpleNamespace(lines=[SimpleNamespace(angle=0)]),
    )
    signature = hatch_signature(hatch)
    assert signature["pattern"] == "ANSI31"
    assert signature["angle"] == 45.0
    assert signature["angle_bucket"] == 45.0
    assert signature["scale"] == 2.0
    assert signature_key(signature) == ("ANSI31", 45.0)
