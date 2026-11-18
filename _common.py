"""Shared helpers for the install scripts. Not meant to be run directly."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = REPO_DIR / "config.json"
SHIM_FILE = REPO_DIR / "shim" / "sitecustomize.py"

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
if os.name == "nt":
    os.system("")  # switches the Windows console into ANSI escape mode

_COLOUR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(code):
    return code if _COLOUR else ""


CYAN, GREEN, YELLOW, RED = _c("\033[36m"), _c("\033[32m"), _c("\033[33m"), _c("\033[31m")
BOLD, RESET = _c("\033[1m"), _c("\033[0m")


def header(msg): print(f"\n{BOLD}=== {msg} ==={RESET}\n")
def ok(msg):     print(f"{GREEN}[ OK ]{RESET}  {msg}")
def warn(msg):   print(f"{YELLOW}[WARN]{RESET}  {msg}")
def err(msg):    print(f"{RED}[FAIL]{RESET}  {msg}")
def info(msg):   print(f"{CYAN}[INFO]{RESET}  {msg}")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Every key has a default here; config.json (git-ignored, copied from
# config.example.json) overrides whichever keys it sets.
DEFAULTS = {
    "mpc": {
        # AutoScript's own documented default address for the microscope PC.
        "host": "192.168.0.1",
        "port": 7520,
        # Where AutoScript keeps its client wheels on the microscope PC, reached
        # over the Windows admin share. {host} is filled in at run time.
        "wheel_share_template":
            r"\\{host}\C$\Program Files\Thermo Scientific AutoScript\PythonPackages",
    },
    "env_name": "fibsem-os",
    "python_version": "3.11",
    # A release on PyPI, or "latest" for the newest non-pre-release.
    "fibsem_version": "0.5.3",
    "fibsem_extras": "ui",
    # Local folders checked (in order) for AutoScript wheels when no source is given.
    "wheel_paths": [r"E:\PythonPackages", r"D:\PythonPackages"],
    "source_repo": "https://github.com/fibsem-os/fibsem-os.git",
    "source_ref": "main",
}


def _merge(base, override):
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def save_host(host, path=CONFIG_FILE):
    """Record the microscope PC address in config.json, keeping its other keys."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("mpc", {})["host"] = host
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_config(path=CONFIG_FILE):
    """Return DEFAULTS overlaid with config.json, if one exists."""
    path = Path(path)
    if not path.exists():
        return _merge(DEFAULTS, {})
    try:
        return _merge(DEFAULTS, json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        err(f"{path.name} is not valid JSON: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# conda / mamba
# ---------------------------------------------------------------------------
def conda_cmd():
    """Full path to mamba or conda (mamba preferred).

    On Windows the .exe is preferred: subprocess cannot start a .bat file
    without a shell, and PATH often lists condabin\\conda.bat first, which
    fails with "_winapi.CreateProcess ... file not found".
    """
    for name in ("mamba", "conda"):
        if sys.platform == "win32":
            exe = shutil.which(name + ".exe")
            if exe:
                return exe
        path = shutil.which(name)
        if path:
            return path
    # Not on PATH, e.g. a fresh Miniforge installed without touching PATH and
    # run through its own python.exe: look beside this interpreter, then at
    # what an activated prompt exports.
    root = Path(sys.prefix)
    if sys.platform == "win32":
        beside = [root / "Library" / "bin" / "mamba.exe", root / "Scripts" / "conda.exe"]
    else:
        beside = [root / "bin" / "mamba", root / "bin" / "conda"]
    for candidate in beside + [Path(os.environ.get("CONDA_EXE", ""))]:
        if candidate.name and candidate.is_file():
            return str(candidate)
    return None


def require_conda():
    conda = conda_cmd()
    if not conda:
        err("Neither mamba nor conda is on PATH.")
        info("Install Miniforge (https://conda-forge.org/download/) and run this "
             "from a Miniforge Prompt.")
        sys.exit(1)
    return conda


def run(cmd, check=True, capture=False, env=None):
    print(f"  > {' '.join(str(c) for c in cmd)}")
    return subprocess.run([str(c) for c in cmd], check=check,
                          capture_output=capture, text=True, env=env)


def list_env_prefixes(conda):
    """Full paths of the conda envs. Uses --json: the text output of
    `info --envs` differs between conda, mamba 1.x and mamba 2.x."""
    try:
        r = subprocess.run([conda, "info", "--envs", "--json"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return []
        return [Path(p) for p in json.loads(r.stdout).get("envs", [])]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []


def list_conda_envs(conda):
    """Env names known to conda."""
    return [p.name for p in list_env_prefixes(conda)]


def env_prefix(conda, env):
    """The env's folder, or None."""
    for prefix in list_env_prefixes(conda):
        if prefix.name == env:
            return prefix
    return None


def env_environ(prefix):
    """os.environ as `conda activate` would set it for prefix: its tools first
    on PATH (Windows also needs the Library folders, for DLLs)."""
    prefix = Path(prefix)
    if sys.platform == "win32":
        dirs = [prefix, prefix / "Library" / "mingw-w64" / "bin", prefix / "Library" / "usr" / "bin",
                prefix / "Library" / "bin", prefix / "Scripts", prefix / "bin"]
    else:
        dirs = [prefix / "bin"]
    environ = dict(os.environ)
    environ["PATH"] = os.pathsep.join(str(d) for d in dirs) + os.pathsep + environ.get("PATH", "")
    environ["CONDA_PREFIX"] = str(prefix)
    environ["CONDA_DEFAULT_ENV"] = prefix.name
    environ.pop("PYTHONHOME", None)
    return environ


def conda_run(conda, env, args, check=True, capture=False):
    """Run a command from a conda env, as if the env were activated.

    Deliberately not `conda run`: on Windows that writes the command into a
    temporary .bat file, which splits multi-line `python -c` code into separate
    cmd.exe lines and mangles % ^ & | < > and quotes; mamba 2.x also buffers all
    output until the command ends. Starting the env's own executable with the
    env's PATH has neither problem.
    """
    prefix = env_prefix(conda, env)
    if prefix is None:
        err(f"Conda env '{env}' not found.")
        sys.exit(1)
    environ = env_environ(prefix)
    args = [str(a) for a in args]
    exe = shutil.which(args[0], path=environ["PATH"]) or args[0]
    cmd = [exe] + args[1:]
    if capture:
        return subprocess.run(cmd, check=check, capture_output=True, text=True, env=environ)
    return run(cmd, check=check, env=environ)


def conda_env_exists(conda, env):
    return env in list_conda_envs(conda)


def active_env():
    """The activated conda env, unless it is base."""
    name = os.environ.get("CONDA_DEFAULT_ENV")
    return name if name and name != "base" else None


def require_env(conda, env):
    if conda_env_exists(conda, env):
        return
    err(f"Conda env '{env}' not found.")
    envs = list_conda_envs(conda)
    if envs:
        info(f"Available envs: {', '.join(envs)}")
    info(f"Run install.py to create it, or pass --env <name>.")
    sys.exit(1)


def env_site_packages(conda, env):
    """The env's site-packages directory.

    sysconfig rather than site.getsitepackages(): on Windows the latter lists
    the env root first, not site-packages.
    """
    r = conda_run(conda, env, ["python", "-c",
                               "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                  capture=True)
    lines = [line for line in r.stdout.splitlines() if line.strip()]
    return Path(lines[-1].strip())


# ---------------------------------------------------------------------------
# AutoScript wheels
# ---------------------------------------------------------------------------
# What fibsemOS imports, directly or through the client.
REQUIRED_WHEELS = (
    "autoscript_sdb_microscope_client",
    "autoscript_core",
    "thermoscientific_logging",
)
# Shipped by Thermo Fisher alongside, never imported by fibsemOS.
OPTIONAL_WHEELS = (
    "autoscript_toolkit",
    "autoscript_sdb_microscope_client_tests",
)


def resolve_share(config, host=None):
    """The UNC path to the wheel folder on the microscope PC."""
    mpc = config["mpc"]
    return mpc["wheel_share_template"].format(host=host or mpc["host"])


def _version_key(wheel):
    # <name>-<version>-<tags>.whl
    parts = wheel.name.split("-")
    version = parts[1] if len(parts) > 1 else ""
    return [int(x) if x.isdigit() else -1 for x in version.split(".")]


def find_wheel(src, package):
    """The newest wheel for a package in src, or None."""
    # Wheel file names spell the project with underscores (PEP 427). The exact
    # first-field match stops "..._client-*" also picking up "..._client_tests-*".
    found = [w for w in Path(src).glob(f"{package}*.whl")
             if w.name.split("-")[0] == package]
    return max(found, key=_version_key) if found else None


def collect_wheels(src, include_optional=True):
    """(wheels to install, required packages missing) for a wheel folder."""
    wheels, missing = [], []
    for package in REQUIRED_WHEELS:
        wheel = find_wheel(src, package)
        if wheel:
            wheels.append(wheel)
        else:
            missing.append(package)
    if include_optional:
        for package in OPTIONAL_WHEELS:
            wheel = find_wheel(src, package)
            if wheel:
                wheels.append(wheel)
    return wheels, missing


def wheel_dir_reachable(src):
    """True if src is a folder; otherwise explain and return False."""
    if Path(src).is_dir():
        return True
    err(f"Wheel folder not reachable: {src}")
    if str(src).startswith("\\\\"):
        info("For a share on the microscope PC: is it on, is the path right, and "
             "are credentials cached? See docs/share-access.md.")
    return False


def install_wheels(conda, env, src, include_optional=True, dry_run=False):
    """pip-install the AutoScript wheels from src into env. Returns success."""
    if not wheel_dir_reachable(src):
        return False
    wheels, missing = collect_wheels(src, include_optional)
    if missing:
        err(f"Required wheel(s) missing from {src}: {', '.join(missing)}")
        return False
    for wheel in wheels:
        info(f"{'[dry-run] ' if dry_run else ''}{wheel.name}")
    if dry_run:
        return True
    # --no-deps: the wheels declare none; their imports (numpy, Pillow, ...)
    # arrive with fibsemOS. --force-reinstall so a version change always lands.
    r = conda_run(conda, env, ["python", "-m", "pip", "install", "--no-deps",
                               "--force-reinstall"] + [str(w) for w in wheels], check=False)
    return r.returncode == 0


# ---------------------------------------------------------------------------
# fibsemOS status, run inside the env
# ---------------------------------------------------------------------------
# The AutoScript driver moved between releases (fibsem/microscope.py in 0.5.x,
# fibsem/drivers/autoscript/microscope.py from 0.6), so try both.
STATUS_SNIPPET = r"""
import importlib, sys
def show(label, value): print(f"  {label:<14}{value}")
failed = False
try:
    import fibsem
    show("fibsem", getattr(fibsem, "__version__", "installed"))
except Exception as e:
    show("fibsem", f"IMPORT FAILED: {type(e).__name__}: {e}"); failed = True
try:
    importlib.import_module("fibsem.applications.autolamella")
    show("autolamella", "ok")
except Exception as e:
    show("autolamella", f"IMPORT FAILED: {type(e).__name__}: {e}"); failed = True
driver = None
for name in ("fibsem.drivers.autoscript.microscope", "fibsem.microscope"):
    try:
        driver = importlib.import_module(name); break
    except Exception:
        continue
if driver is None:
    show("AutoScript", "driver module not found")
elif getattr(driver, "THERMO_API_AVAILABLE", False):
    show("AutoScript", f"available, version {getattr(driver, 'AUTOSCRIPT_VERSION', '?')}")
else:
    why = getattr(driver, "THERMO_API_IMPORT_ERROR", None) or "client not importable"
    show("AutoScript", f"NOT available ({why})")
sys.exit(1 if failed else 0)
"""
