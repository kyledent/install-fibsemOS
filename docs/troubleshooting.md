# Troubleshooting

Problems met installing fibsemOS on locked-down Windows support PCs, and what
the scripts do about them.

## `fibsem-autolamella-ui` / `fibsem_ui` will not start

**Symptom:** the command is found but blocked, or nothing happens. The error
mentions policy, access, or "This program is blocked".

**Cause:** pip installs each command as a small `.exe` in the env's `Scripts`
folder. Software Restriction Policies or AppLocker often block `.exe` files in
user-writable folders.

**Fix:** start the app through `python.exe` instead:

| Command | Starts |
|---|---|
| `python launch.py` | AutoLamella |
| `python launch.py fibsem` | the fibsemOS UI |
| `python launch.py --list` | nothing; lists every fibsemOS command |

`launch.py` looks the command up by name and calls the same function the `.exe`
would, so it works whichever fibsemOS release is installed. If `python.exe` in
the env is blocked too, the env lives in a disallowed folder; ask IT to
allow-list it, or create the env somewhere that is allowed.

## `--no-capture-output` is not a recognised command

**Cause:** mamba 2.x removed the `--no-capture-output` flag that conda and
mamba 1.x accept on `run`.

**Fix:** none needed. The scripts check `run --help` and only pass the flag
when it is supported. Without it, each step's output appears when the step
finishes rather than live.

## `_winapi.CreateProcess(...)`: file not found

**Cause:** Python's `subprocess` cannot start a `.bat` file without a shell,
and `conda` on PATH is often `condabin\conda.bat`.

**Fix:** none needed. The scripts look for `mamba.exe` / `conda.exe` first.
If it still happens, check that `where conda` lists an `.exe` (run from a
Miniforge Prompt).

## "Conda env not found" although it is activated

**Cause:** the text output of `conda info --envs` differs between conda,
mamba 1.x and mamba 2.x.

**Fix:** none needed. The scripts read `--json` output instead. `verify.py`,
`launch.py` and `install_autoscript_wheels.py` also use the activated env by
default. When an env really is missing they list the ones that exist.

## `module 'collections' has no attribute 'Mapping'`

The AutoScript client predates Python 3.10. See
[autoscript-wheels.md](autoscript-wheels.md#python-310-and-the-collections-shim).
`python check_autoscript_compat.py` tells you whether the shim is needed and
whether it is working.

## "AutoScript X found. Please update your AutoScript version"

fibsemOS has a minimum AutoScript version: 4.7 up to 0.5.x, and 4.9 from 0.6.
Upgrade AutoScript on the MPC, which needs Thermo Fisher, or install a fibsemOS
release that accepts your version:

```
python install.py --fibsem-version 0.5.3
```

## Detector brightness/contrast SKIP in the poll test

`test_autoscript_poll.py` reads them from whichever detector is active in xT.
Detectors such as "External" have no brightness or contrast. Depending on the
AutoScript release, the server reports that as "doesn't have a brightness
parameter" or as "The method or operation is not implemented". Both are
reported as SKIP. To confirm the controls work, select ETD (or similar) in xT
and re-run.

## Installing on a PC with no internet

On a connected PC with the **same Python version**:

```
pip download "fibsem[ui]==0.5.3" -d pkg
```

Carry `pkg` and your AutoScript wheels across, then on the offline PC:

```
conda create -n fibsem-os python=3.11 pip -y
conda run -n fibsem-os python -m pip install --no-index --find-links pkg "fibsem[ui]==0.5.3"
python install.py --wheels E:\PythonPackages
```

In the last step pip finds fibsemOS already installed and does not reach the
network. The script still adds the shim and the AutoScript wheels.
