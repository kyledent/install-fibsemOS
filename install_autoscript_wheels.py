#!/usr/bin/env python3
"""
Install (or update) the AutoScript client wheels in an existing fibsemOS env.

Use after an AutoScript upgrade on the microscope PC, or when install.py was
run with --skip-autoscript.

    python install_autoscript_wheels.py --from-mpc            # MPC admin share
    python install_autoscript_wheels.py --from-mpc 10.0.0.5   # another host
    python install_autoscript_wheels.py E:\\PythonPackages     # local folder / USB
    python install_autoscript_wheels.py --from-mpc --list     # look, don't install

The client version should match the AutoScript server on the microscope PC,
so take the wheels from that PC (or a copy of its PythonPackages folder).
"""

import argparse
import sys

import _common as c


def main():
    cfg = c.load_config()
    default_env = c.active_env() or cfg["env_name"]
    p = argparse.ArgumentParser(description="Install AutoScript client wheels.")
    p.add_argument("source", nargs="?", help="folder holding the .whl files")
    p.add_argument("--from-mpc", nargs="?", const="", metavar="HOST",
                   help=f"use the microscope PC's share (default host: {cfg['mpc']['host']})")
    p.add_argument("--env", default=default_env, help=f"default: {default_env}")
    p.add_argument("--list", action="store_true", help="list the wheels found and stop")
    p.add_argument("--dry-run", action="store_true", help="show what would be installed")
    p.add_argument("--no-optional-wheels", action="store_true",
                   help="install only the 3 wheels fibsemOS needs")
    args = p.parse_args()

    if args.from_mpc is not None:
        src = c.resolve_share(cfg, args.from_mpc or None)
    elif args.source:
        src = args.source
    else:
        p.error("give a folder, or --from-mpc")

    c.header("AutoScript wheels")
    c.info(f"source : {src}")

    if args.list:
        if not c.wheel_dir_reachable(src):
            sys.exit(1)
        for package in c.REQUIRED_WHEELS + c.OPTIONAL_WHEELS:
            kind = "required" if package in c.REQUIRED_WHEELS else "optional"
            wheel = c.find_wheel(src, package)
            (c.ok if wheel else (c.err if kind == "required" else c.warn))(
                f"[{kind}] {wheel.name if wheel else package + ' (not found)'}")
        return

    conda = c.require_conda()
    c.info(f"env    : {args.env}")
    c.require_env(conda, args.env)
    if not c.install_wheels(conda, args.env, src,
                            include_optional=not args.no_optional_wheels,
                            dry_run=args.dry_run):
        sys.exit(1)
    if args.dry_run:
        return

    c.header("Check")
    r = c.conda_run(conda, args.env, ["python", "-c",
        "import autoscript_sdb_microscope_client.build_information as b; "
        "print('  AutoScript client', b.INFO_VERSIONSHORT)"], check=False)
    if r.returncode:
        c.err("The client does not import. Run check_autoscript_compat.py in the env.")
        sys.exit(1)
    c.ok("Done. Restart fibsemOS to pick up the new client.")


if __name__ == "__main__":
    main()
