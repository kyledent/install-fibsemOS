"""Compatibility shim for older AutoScript client wheels on Python 3.10+.

install.py copies this file into the fibsemOS env's site-packages, where
Python runs it at start-up, before any other code.

Python 3.10 removed the aliases `collections.Mapping`, `collections.Callable`
and friends (they live in `collections.abc` since 3.3). AutoScript clients
written for Python 3.5-3.8 can still use the old names and then fail to import
with "module 'collections' has no attribute 'Mapping'".

Each alias is added only when missing, so on a client that does not need it
this does nothing. Run check_autoscript_compat.py to see whether yours does.
Remove the file from site-packages to uninstall.
"""
import collections
import collections.abc

for _name in (
    "Callable", "Iterator", "Iterable", "Mapping", "MutableMapping",
    "MutableSequence", "Sequence", "Set", "MutableSet",
):
    if not hasattr(collections, _name):
        setattr(collections, _name, getattr(collections.abc, _name))
