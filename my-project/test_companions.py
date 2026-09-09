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
    assert luno["expressions"]["wave"].endswith("luno-wave.png")
    assert normalize_companion_id("nope") == "luna"
    assert normalize_companion_id("REN") == "ren"
    print("OK companions catalog", len(rows))


if __name__ == "__main__":
    test_catalog_has_luna_and_animals()
    print("ALL companion tests passed")
