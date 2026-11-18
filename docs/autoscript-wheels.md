# AutoScript client wheels

AutoScript is Thermo Fisher's licensed scripting interface. Its server runs on
the microscope PC (MPC) next to xT; clients connect to it over TCP, port 7520
by default. The client is a set of pure-Python wheels (`py3-none-any`), so it
installs on any OS and any Python, including a support PC that has no
AutoScript installation of its own.

This repository never contains those wheels. You copy them from your own
licensed installation.

## Where they are

On the microscope PC:

```
C:\Program Files\Thermo Scientific AutoScript\PythonPackages\
```

Over the network, through the Windows admin share (see
[share-access.md](share-access.md)):

```
\\<mpc-host>\C$\Program Files\Thermo Scientific AutoScript\PythonPackages\
```

## Which ones fibsemOS needs

| Wheel | Needed | Why |
|---|---|---|
| `autoscript_sdb_microscope_client` | yes | The API fibsemOS calls (`SdbMicroscopeClient`, enumerations, structures) |
| `autoscript_core` | yes | Imported by the client: transport, serialisation, exceptions |
| `thermoscientific_logging` | yes | Imported by `autoscript_core.logging` |
| `autoscript_toolkit` | no | Not imported by fibsemOS |
| `autoscript_sdb_microscope_client_tests` | no | Thermo Fisher's test fixtures (~40 MB) |
| `autoscript_toolkit_*_extension` | no | Optional add-ons in newer releases |

`install.py` installs the three required wheels and, unless you pass
`--no-optional-wheels`, the toolkit and tests wheels as well. Both of those are
optional because fibsemOS does not import them, and the tests wheel is large.

The client and core packages are versioned separately. For example, a 4.9
install ships `autoscript_sdb_microscope_client-4.9.0` alongside
`autoscript_core-5.21.0` and `thermoscientific_logging-5.21.0`.

## Matching versions

Take the wheels from the microscope PC you will connect to, so the client
matches its AutoScript server. After an AutoScript upgrade on the MPC, run:

```
python install_autoscript_wheels.py --from-mpc
```

fibsemOS refuses AutoScript clients older than its minimum: 4.7 up to
fibsemOS 0.5.x, and 4.9 from 0.6.

## Dependencies

The wheels declare no dependencies, so they are installed with `--no-deps`.
What they import at run time (numpy, Pillow and similar) comes in with
fibsemOS. That is why `install.py` installs fibsemOS first and the wheels second.

## Python 3.10+ and the collections shim

Python 3.10 removed `collections.Mapping` and similar aliases. AutoScript
clients written for Python 3.5–3.8 can still use them, and then fail with:

```
AttributeError: module 'collections' has no attribute 'Mapping'
```

`install.py` puts [`shim/sitecustomize.py`](../shim/sitecustomize.py) into the
env's site-packages. Python runs it at start-up, and it restores only the
aliases that are missing, so it has no effect on clients that don't need it.

The 4.9.0 client (`autoscript_core` 5.21.0) has been checked and imports on
Python 3.12 without the shim, and its source has no legacy `collections.*`
uses. The shim is for older clients, from the 4.6 era, which fibsemOS 0.5.x
still accepts. To check yours:

```
conda activate fibsem-os
python check_autoscript_compat.py
```

## Alternatives fibsemOS supports

fibsemOS can also use AutoScript from AutoScript's own Python environment on
the same PC, or from a folder named by `FIBSEM_AUTOSCRIPT_PATH`. Packages
installed into the fibsemOS env itself, which is what this repo does, take
precedence over both. Installing the wheels into the env is the right choice
on a support PC without its own AutoScript, and it means fibsemOS does not
depend on a network share each time it starts.
