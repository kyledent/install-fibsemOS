#!/usr/bin/env python3
"""
Start a fibsemOS application without its .exe launcher.

pip puts a small .exe for each fibsemOS command (fibsem-autolamella-ui,
fibsem_ui, ...) in the env's Scripts folder. Where software restriction
policies or AppLocker block .exe files in user-writable folders, those fail
to start. This script looks the command up by name and calls the same Python
function the .exe would, so only python.exe has to be allowed to run.

    python launch.py                  # AutoLamella (fibsem-autolamella-ui)
    python launch.py fibsem           # the fibsemOS UI (fibsem_ui)
    python launch.py <console-script> # any fibsemOS command, by name
    python launch.py --list           # the commands this install provides

Run it with the env activated. From another env (base, say) it re-runs itself
inside the configured one.
"""

import argparse
import sys

ALIASES = {
    "autolamella": "fibsem-autolamella-ui",
    "fibsem": "fibsem_ui",
}


def fibsem_scripts():
    from importlib.metadata import entry_points
    return {ep.name: ep for ep in entry_points(group="console_scripts")
            if ep.value.split(".")[0] == "fibsem"}


def relaunch_in_env(env):
    """fibsemOS is not in this Python: re-run this script with the env's python."""
    import os

    import _common as c
    if os.environ.get("FIBSEM_LAUNCH_RELAUNCHED"):
        c.err(f"fibsemOS is not installed in '{env}' either. Run install.py first.")
        sys.exit(1)
    conda = c.require_conda()
    c.require_env(conda, env)
    c.info(f"fibsemOS is not in this Python; starting it in '{env}'.")
    os.environ["FIBSEM_LAUNCH_RELAUNCHED"] = "1"  # inherited by the child; stops a loop
    r = c.conda_run(conda, env, ["python", __file__] + sys.argv[1:], check=False)
    sys.exit(r.returncode)


def main():
    p = argparse.ArgumentParser(description="Start a fibsemOS application.")
    p.add_argument("app", nargs="?", default="autolamella",
                   help="autolamella (default), fibsem, or a console-script name")
    p.add_argument("--env", help="env to use if this Python has no fibsemOS")
    p.add_argument("--list", action="store_true", help="list the available commands")
    args, rest = p.parse_known_args()

    try:
        import fibsem  # noqa: F401
    except ImportError:
        import _common as c
        relaunch_in_env(args.env or c.active_env() or c.load_config()["env_name"])

    scripts = fibsem_scripts()
    if args.list:
        for name in sorted(scripts):
            print(f"  {name:<28} {scripts[name].value}")
        return

    name = ALIASES.get(args.app, args.app)
    if name not in scripts:
        print(f"No fibsemOS command '{name}'. Available: {', '.join(sorted(scripts))}")
        sys.exit(1)
    sys.argv = [name] + rest
    sys.exit(scripts[name].load()())


if __name__ == "__main__":
    main()
