#!/usr/bin/env python3
"""
Does this AutoScript client need the collections shim on this Python?

Imports the client twice, each in a fresh interpreter:
  1. with the legacy `collections.Mapping`-style aliases removed (Python 3.10+
     as it ships, which is what the client sees without the shim);
  2. normally (with shim/sitecustomize.py, if it is installed).

Run it with the fibsemOS env activated:

    python check_autoscript_compat.py
"""

import subprocess
import sys

import _common as c

ALIASES = ("Callable", "Iterator", "Iterable", "Mapping", "MutableMapping",
           "MutableSequence", "Sequence", "Set", "MutableSet")

IMPORT = ("import autoscript_sdb_microscope_client as a; "
          "print(a.build_information.INFO_VERSIONSHORT)")

WITHOUT_SHIM = ("import collections\n"
                f"for n in {ALIASES!r}: collections.__dict__.pop(n, None)\n"
                + IMPORT)


def attempt(code):
    """(imported?, version string or the last line of the error)"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if r.returncode == 0:
        return True, r.stdout.strip()
    lines = r.stderr.strip().splitlines()
    return False, lines[-1] if lines else f"exit code {r.returncode}"


def main():
    c.header("AutoScript compatibility")
    c.info(f"Python {sys.version.split()[0]}  ({sys.executable})")

    bare_ok, bare_out = attempt(WITHOUT_SHIM)
    normal_ok, normal_out = attempt(IMPORT)

    (c.ok if bare_ok else c.warn)(
        f"without the shim: {'imports, AutoScript ' + bare_out if bare_ok else bare_out}")
    (c.ok if normal_ok else c.err)(
        f"as installed:     {'imports, AutoScript ' + normal_out if normal_ok else normal_out}")

    print()
    if bare_ok and normal_ok:
        c.ok("This client does not need the shim. Keeping it installed is harmless.")
    elif normal_ok:
        c.ok("This client needs the shim, and it is working. Keep it installed.")
    elif bare_ok:
        c.err("The client imports bare but not as installed: the env's sitecustomize.py "
              "is breaking it. Compare it with shim/sitecustomize.py.")
    else:
        c.err("The client does not import either way.")
        if "collections" in normal_out:
            c.info("Install the shim: python install.py --skip-autoscript")
        elif "No module named" in normal_out:
            c.info("A client package is missing: run install_autoscript_wheels.py.")
        sys.exit(1)


if __name__ == "__main__":
    main()
