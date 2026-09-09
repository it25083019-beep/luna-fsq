# -*- coding: utf-8 -*-
from companions import get_companion, list_companions, normalize_companion_id


def test_catalog_has_luna_and_animals():
    rows = list_companions()
    ids = [c["id"] for c in rows]
    assert ids[0] == "luna"
    for need in ("luno", "ren", "hachi", "momo", "taro", "ponta"):
        assert need in ids
    animal = [c for c in rows if c.get("kind") == "animal"]
    assert {c["id"] for c in animal} == {"hachi", "momo", "taro", "ponta"}
    luno = get_companion("luno")
    assert luno["themes"]["health"].endswith("health-luno.png")
    assert luno["themes"]["money"].endswith("money-luno.png")
    voices = {c["id"]: (c.get("voice") or {}).get("gemini_name") for c in rows}
    assert voices["luna"] == "Gacrux"
    assert voices["luno"] == "Leda"
    assert voices["ren"] == "Charon"
    assert len(set(voices.values())) == len(voices)
    assert (get_companion("ren").get("voice") or {}).get("browser_pitch", 1) < 0.7
    assert normalize_companion_id("nope") == "luna"
    assert normalize_companion_id("REN") == "ren"
    print("OK companions catalog", len(rows))


if __name__ == "__main__":
    test_catalog_has_luna_and_animals()
    print("ALL companion tests passed")
