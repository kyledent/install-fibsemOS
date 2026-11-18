import collections
import collections.abc
import runpy

import _common as c

ALIASES = ("Callable", "Iterator", "Iterable", "Mapping", "MutableMapping",
           "MutableSequence", "Sequence", "Set", "MutableSet")


def test_shim_restores_aliases_and_leaves_existing_ones(monkeypatch):
    for name in ALIASES:
        monkeypatch.delitem(collections.__dict__, name, raising=False)
    sentinel = object()
    monkeypatch.setitem(collections.__dict__, "Mapping", sentinel)

    runpy.run_path(str(c.SHIM_FILE))

    assert collections.Mapping is sentinel  # never overwritten
    for name in ALIASES:
        if name != "Mapping":
            assert getattr(collections, name) is getattr(collections.abc, name)
