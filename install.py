#!/usr/bin/env python3
"""
Install fibsemOS on a Windows 10/11 support PC that drives a Thermo Fisher
FIB/SEM through AutoScript (4.9 or later) on the microscope PC (MPC).

Run from a Miniforge Prompt; the base environment is fine:

    python install.py --from-mpc                 # wheels straight from the MPC's share
    python install.py --wheels E:\\PythonPackages  # wheels from a local copy / USB stick
    python install.py --skip-autoscript          # fibsemOS only (simulator, or add later)

    python install.py --fibsem-version 0.6.0rc1  # another release ("latest" = newest)
    python install.py --extras ui,ml             # add the ML extra (PyTorch, ~2 GB)
    python install.py --from-source              # editable clone of fibsem-os (main)

Steps: create the conda env, install the collections shim, install fibsemOS,
install the AutoScript client wheels, check the imports.
Every step is safe to re-run.
"""

import argparse
import shutil
import sys
from pathlib import Path

import _common as c


def parse_args(cfg):
    p = argparse.ArgumentParser(
        description="Install fibsemOS + the AutoScript client on a Windows support PC.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--env", default=cfg["env_name"],
                   help=f"conda env to create or update (default: {cfg['env_name']})")
    p.add_argument("--python", default=cfg["python_version"],
                   help=f"Python version for a new env (default: {cfg['python_version']})")
    p.add_argument("--fibsem-version", default=cfg["fibsem_version"],
                   help=f'PyPI release, or "latest" (default: {cfg["fibsem_version"]})')
    p.add_argument("--extras", default=cfg["fibsem_extras"],
                   help=f"fibsem extras, comma separated (default: {cfg['fibsem_extras']})")
    p.add_argument("--constraints", metavar="FILE",
                   help="pip constraints file, to reproduce a known-good install")
    p.add_argument("--from-source", nargs="?", const=cfg["source_ref"], metavar="REF",
                   help=f"clone fibsem-os and install it editable (default ref: "
                        f"{cfg['source_ref']}) instead of from PyPI")
    p.add_argument("--source-dir", default=str(c.REPO_DIR / "fibsem-os"),
                   help="where --from-source clones to")

    src = p.add_mutually_exclusive_group()
    src.add_argument("--from-mpc", nargs="?", const="", metavar="HOST",
                     help="AutoScript wheels from the microscope PC's admin share "
                          f"(default host: {cfg['mpc']['host']})")
    src.add_argument("--wheels", metavar="DIR", help="AutoScript wheels from a folder")
    src.add_argument("--skip-autoscript", action="store_true",
                     help="do not install the AutoScript client")

    p.add_argument("--no-optional-wheels", action="store_true",
                   help="install only the 3 wheels fibsemOS needs")
    p.add_argument("--skip-shim", action="store_true",
                   help="do not install the collections shim (sitecustomize.py)")
    p.add_argument("--yes", "-y", action="store_true",
                   help="never prompt (unattended / CI)")
    return p.parse_args()


def ensure_env(conda, args, need_git):
    c.header(f"Conda env '{args.env}'")
    if c.conda_env_exists(conda, args.env):
        c.ok(f"'{args.env}' exists; updating it in place.")
        if need_git and c.conda_run(conda, args.env, ["git", "--version"],
                                    check=False, capture=True).returncode != 0:
            c.run([conda, "install", "-n", args.env, "-c", "conda-forge", "git", "-y"])
        return
    packages = [f"python={args.python}", "pip"] + (["git"] if need_git else [])
    c.run([conda, "create", "-n", args.env, "-c", "conda-forge", "-y"] + packages)
    c.ok(f"Created '{args.env}'.")


def install_shim(conda, env):
    c.header("Collections shim")
    dst = c.env_site_packages(conda, env) / "sitecustomize.py"
    new = c.SHIM_FILE.read_text(encoding="utf-8")
    if dst.exists():
        if dst.read_text(encoding="utf-8", errors="replace") == new:
            c.ok(f"Already installed: {dst}")
            return
        shutil.copy2(dst, dst.with_suffix(".py.bak"))
        c.warn(f"An existing sitecustomize.py was backed up to {dst.name}.bak")
    shutil.copy2(c.SHIM_FILE, dst)
    c.ok(f"Installed: {dst}")


def install_fibsem(conda, args, cfg):
    c.header("fibsemOS")
    pip = ["python", "-m", "pip", "install"]  # `python -m pip`: no pip.exe shim
    if args.constraints:
        pip += ["-c", str(Path(args.constraints).resolve())]

    if args.from_source is not None:
        src = Path(args.source_dir).resolve()
        if (src / ".git").exists():
            c.info(f"Updating {src} to {args.from_source}")
            c.conda_run(conda, args.env, ["git", "-C", src, "fetch", "origin"])
            c.conda_run(conda, args.env, ["git", "-C", src, "checkout", args.from_source])
            c.conda_run(conda, args.env, ["git", "-C", src, "pull", "--ff-only"], check=False)
        else:
            c.conda_run(conda, args.env, ["git", "clone", "--branch", args.from_source,
                                          cfg["source_repo"], src])
        spec = ["-e", f"{src}[{args.extras}]"]
    else:
        spec = [f"fibsem[{args.extras}]"]
        if args.fibsem_version.lower() != "latest":
            spec = [f"fibsem[{args.extras}]=={args.fibsem_version}"]

    c.conda_run(conda, args.env, pip + spec)
    c.ok("fibsemOS installed.")


def pick_wheel_source(args, cfg):
    """A wheel folder to install from, or None to skip."""
    if args.skip_autoscript:
        return None
    if args.from_mpc is not None:
        return c.resolve_share(cfg, args.from_mpc or None)
    if args.wheels:
        return args.wheels
    for candidate in cfg["wheel_paths"]:
        if Path(candidate).is_dir() and c.find_wheel(candidate, c.REQUIRED_WHEELS[0]):
            c.info(f"Found AutoScript wheels in {candidate}")
            return candidate
    if args.yes or not sys.stdin.isatty():
        return None
    print("\n  Where are the AutoScript wheels? On the microscope PC they are in")
    print(r"    C:\Program Files\Thermo Scientific AutoScript\PythonPackages")
    print(f"  Over the network that is usually {c.resolve_share(cfg)}")
    answer = input("  Folder (blank to skip): ").strip().strip('"')
    return answer or None


def main():
    cfg = c.load_config()
    args = parse_args(cfg)
    conda = c.require_conda()

    c.header("install_fibsem-os_win11")
    c.info(f"conda/mamba : {conda}")
    c.info(f"env         : {args.env}")
    c.info(f"fibsemOS    : "
           f"{'source @ ' + args.from_source if args.from_source is not None else args.fibsem_version}"
           f"  [{args.extras}]")

    ensure_env(conda, args, need_git=args.from_source is not None)
    if not args.skip_shim:
        install_shim(conda, args.env)
    install_fibsem(conda, args, cfg)

    c.header("AutoScript client")
    wheel_src = pick_wheel_source(args, cfg)
    autoscript_ok = None
    if wheel_src is None:
        c.warn("Skipped. Add it later with install_autoscript_wheels.py.")
    else:
        c.info(f"From: {wheel_src}")
        autoscript_ok = c.install_wheels(conda, args.env, wheel_src,
                                         include_optional=not args.no_optional_wheels)
        (c.ok if autoscript_ok else c.err)(
            "AutoScript wheels installed." if autoscript_ok else "AutoScript wheel install failed.")

    c.header("Check")
    status = c.conda_run(conda, args.env, ["python", "-c", c.STATUS_SNIPPET], check=False)

    c.header("Next")
    mpc = cfg["mpc"]
    print("  Check the install, poll the instrument (read-only), start AutoLamella:\n")
    print(f"    conda activate {args.env}")
    print("    python verify.py --check-network")
    print("    python test_autoscript_poll.py")
    print("    python launch.py")
    print(f"\n  In fibsemOS connect to {mpc['host']}, port {mpc['port']}, manufacturer Thermo.")

    if status.returncode != 0 or autoscript_ok is False:
        c.err("Finished with errors (see above).")
        sys.exit(1)
    c.ok("Done.")


if __name__ == "__main__":
    main()
