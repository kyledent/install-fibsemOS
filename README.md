# install_fibsem-os_win11

Install [fibsemOS](https://github.com/fibsem-os/fibsem-os) (including
AutoLamella) on a **Windows 10/11 support PC** that controls a **Thermo Fisher
FIB/SEM** through **AutoScript**. The microscope PC itself is left untouched.

```
 Support PC (Windows 10/11)                 Microscope PC (MPC)
 ┌─────────────────────────────┐            ┌──────────────────────────┐
 │ conda env "fibsem-os"       │            │ xT                       │
 │   fibsemOS + AutoLamella    │  TCP 7520  │ AutoScript server        │
 │   AutoScript client wheels ─┼───────────►│                          │
 └─────────────────────────────┘            └──────────────────────────┘
```

AutoScript's client is pure Python and talks to the server over the network,
so it does not need AutoScript installed locally. These scripts copy the
client from the MPC into a conda env alongside fibsemOS, and work around the
problems that tend to come up on locked-down Windows PCs.

> Not affiliated with Thermo Fisher Scientific or the fibsemOS project.
> AutoScript is licensed software; this repository contains none of it.

## Requirements

- Windows 10 or 11 on the support PC. Windows 7 cannot run Python 3.10+.
- [Miniforge](https://conda-forge.org/download/), to get `conda`/`mamba`
  without licensing conditions. `bootstrap.cmd` installs it for you if it is
  missing, with no administrator rights needed.
- Network access from the support PC to the MPC on TCP 7520.
- AutoScript server on the MPC, licensed and running. fibsemOS 0.5.x accepts
  AutoScript 4.7+; 0.6+ needs 4.9+.
- The AutoScript client wheels, either from the MPC's share or from a copy.
  See [docs/autoscript-wheels.md](docs/autoscript-wheels.md).
- Internet access for the first install (PyPI). See
  [offline install](docs/troubleshooting.md#installing-on-a-pc-with-no-internet).

## Quick start (fresh PC, from the downloaded ZIP)

1. On GitHub choose **Code → Download ZIP**.
2. Right-click the ZIP, choose **Properties**, tick **Unblock**, then OK. This
   avoids Windows' "downloaded from the internet" warnings on every script.
3. Extract it anywhere, e.g. `C:\fibsem-install`.
4. Double-click **`bootstrap.cmd`** in the extracted folder.

`bootstrap.cmd` installs Miniforge if the PC has no conda (current user only,
checksum-verified). It then asks for the microscope PC's address and where the
AutoScript wheels are, and installs everything. Pressing Enter at the wheels
question reads them from the MPC's share.

To run it without the questions, open a prompt in the extracted folder:

```
bootstrap.cmd --mpc-host 192.168.0.1 --from-mpc
```

`bootstrap.cmd` takes every `install.py` option, plus `--miniforge-dir DIR`
to choose where Miniforge goes or which install to use.

`--from-mpc` reads the MPC's `C$` share, which needs admin credentials there.
Cache them once with `cmdkey`; see [docs/share-access.md](docs/share-access.md).

## Afterwards

Open the **Miniforge Prompt** from the Start menu, change to the extracted
folder, then check the install (imports, driver status, TCP 7520), poll the
instrument read-only, and start AutoLamella:

```
conda activate fibsem-os
python verify.py --check-network
python test_autoscript_poll.py
python launch.py
```

In fibsemOS, connect with manufacturer **Thermo**, your MPC's address and port
**7520**.

## Quick start (Miniforge already installed)

From a Miniforge Prompt in the repository folder:

```
python install.py --mpc-host 192.168.0.1 --from-mpc
```

Use `--wheels E:\PythonPackages` instead of `--from-mpc` for a local copy of
the wheel folder.

## The scripts

| Script | Does |
|---|---|
| `bootstrap.cmd` / `bootstrap.ps1` | Finds or installs Miniforge, then runs `install.py` with it. The starting point on a fresh PC. |
| `install.py` | Creates the env, installs the collections shim, fibsemOS (a pinned PyPI release or a source checkout) and the AutoScript client, then checks the imports. Safe to re-run. |
| `verify.py` | Checks the env, the shim, every import, the fibsemOS AutoScript driver, and optionally TCP to the MPC. |
| `launch.py` | Starts a fibsemOS app through `python.exe`, for PCs that block pip's `.exe` launchers. |
| `install_autoscript_wheels.py` | Installs or updates just the AutoScript client, e.g. after an AutoScript upgrade. `--list` looks without installing. |
| `check_autoscript_compat.py` | Reports whether your AutoScript client needs the collections shim on this Python. |
| `test_autoscript_poll.py` | Reads ~60 properties over the API without changing anything. `--save-log` keeps a timestamped copy. |

Everything takes `--help`.

## Choosing a fibsemOS version

`install.py` installs the release pinned in `config.json` (`fibsem_version`,
default **0.5.3**, the latest stable release when this was written).

| Command | Installs |
|---|---|
| `python install.py --fibsem-version 0.6.0rc1` | a specific release |
| `python install.py --fibsem-version latest` | the newest non-pre-release |
| `python install.py --from-source` | an editable clone of fibsem-os `main` |
| `python install.py --from-source v0.6.0rc1` | the clone at a tag or branch |
| `python install.py --extras ui,ml` | plus the ML models (PyTorch, ~2 GB) |

To reproduce an install you know works, save its versions once:

```
conda activate fibsem-os
python -m pip freeze > constraints.txt
```

Install elsewhere with `python install.py --constraints constraints.txt`.

## Configuration

Copy `config.example.json` to `config.json`, which git ignores, and change what
you need. Missing keys take the defaults.

| Key | Default | Meaning |
|---|---|---|
| `mpc.host` | `192.168.0.1` | Microscope PC address (AutoScript's own default) |
| `mpc.port` | `7520` | AutoScript server port |
| `mpc.wheel_share_template` | `\\{host}\C$\Program Files\Thermo Scientific AutoScript\PythonPackages` | Where `--from-mpc` looks |
| `env_name` | `fibsem-os` | conda env to create |
| `python_version` | `3.11` | Python for a new env |
| `fibsem_version` | `0.5.3` | PyPI release, or `latest` |
| `fibsem_extras` | `ui` | pip extras for fibsem |
| `wheel_paths` | `E:\PythonPackages`, `D:\PythonPackages` | Folders tried when no wheel source is given |
| `source_repo`, `source_ref` | fibsem-os, `main` | Used by `--from-source` |

## Troubleshooting

[docs/troubleshooting.md](docs/troubleshooting.md) covers blocked `.exe`
launchers, mamba 2.x, `CreateProcess ... file not found`, envs that are
reported missing, the `collections.Mapping` error, the AutoScript version
gate, detector SKIPs in the poll test, and offline installs.

## Development

```
python -m pytest tests
```

CI runs the unit tests on Linux and Windows and two real Windows installs, both
without AutoScript. One runs `install.py` with Miniforge already present. The
other builds the same ZIP GitHub serves, unpacks it, and runs `bootstrap.cmd`
from it, which downloads and installs a fresh Miniforge.

The downloaded ZIP leaves out `tests/` and `.github/` (`export-ignore` in
`.gitattributes`). It also forces CRLF line endings on `.cmd` and `.ps1`
files, which `cmd.exe` needs.

## Licence

Apache License 2.0, see [LICENSE](LICENSE).

fibsemOS is MIT-licensed by its authors and is downloaded, not included.
AutoScript is Thermo Fisher Scientific software, licensed separately.
