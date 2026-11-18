#!/usr/bin/env python3
"""
Check a fibsemOS install: the env, the shim, the imports, the AutoScript
driver, and (optionally) that the microscope PC answers on the AutoScript port.

    python verify.py
    python verify.py --check-network
    python verify.py --env my-env --host 192.168.0.1

Runs from any prompt. Without --env it checks the activated env, or the one
named in config.json.
"""

import argparse
import socket
import sys

import _common as c

results = {"pass": 0, "fail": 0, "warn": 0}


def record(passed, label, optional=False):
    if passed:
        c.ok(label); results["pass"] += 1
    elif optional:
        c.warn(label); results["warn"] += 1
    else:
        c.err(label); results["fail"] += 1


def can_import(conda, env, module):
    r = c.conda_run(conda, env, ["python", "-c", f"import {module}"],
                    check=False, capture=True)
    return r.returncode == 0


def main():
    cfg = c.load_config()
    default_env = c.active_env() or cfg["env_name"]
    p = argparse.ArgumentParser(description="Check a fibsemOS install.")
    p.add_argument("--env", default=default_env, help=f"default: {default_env}")
    p.add_argument("--host", default=cfg["mpc"]["host"])
    p.add_argument("--port", type=int, default=cfg["mpc"]["port"])
    p.add_argument("--check-network", action="store_true",
                   help="also open a TCP connection to the microscope PC")
    p.add_argument("--skip-autoscript", action="store_true",
                   help="do not require the AutoScript client (simulator-only installs)")
    args = p.parse_args()

    conda = c.require_conda()
    c.header("verify")
    c.info(f"conda/mamba : {conda}")
    c.info(f"env         : {args.env}")
    c.require_env(conda, args.env)
    record(True, f"env '{args.env}' exists")

    c.header("Shim")
    try:
        shim = c.env_site_packages(conda, args.env) / "sitecustomize.py"
        record(shim.exists(), f"sitecustomize.py in site-packages", optional=True)
    except Exception as e:  # noqa: BLE001 - diagnostic only
        record(False, f"could not locate site-packages ({e})", optional=True)

    c.header("Imports")
    record(can_import(conda, args.env, "fibsem"), "import fibsem")
    record(can_import(conda, args.env, "fibsem.applications.autolamella"),
           "import fibsem.applications.autolamella")
    for module in c.REQUIRED_WHEELS:
        record(can_import(conda, args.env, module), f"import {module}",
               optional=args.skip_autoscript)

    c.header("fibsemOS status")
    c.conda_run(conda, args.env, ["python", "-c", c.STATUS_SNIPPET], check=False)

    if args.check_network:
        c.header("Network")
        try:
            socket.create_connection((args.host, args.port), timeout=3).close()
            reachable = True
        except OSError:
            reachable = False
        record(reachable, f"TCP {args.host}:{args.port}")
        if not reachable:
            c.info("Is the MPC on, AutoScript's server running, and the port open "
                   "in its firewall?")

    c.header("Summary")
    print(f"  passed {results['pass']}   failed {results['fail']}   warnings {results['warn']}")
    if results["fail"]:
        c.err("Verification failed.")
        sys.exit(1)
    c.ok("Verification passed.")


if __name__ == "__main__":
    main()
