#!/usr/bin/env python3
"""
Read-only poll of the AutoScript API over TCP/IP.

Connects to the microscope PC and reads ~60 properties: system info, vacuum,
stage, both beams, detectors, imaging, patterning, gas injection and the
manipulator. Nothing is set, moved, inserted or milled, so it is safe to run
on an instrument in use.

    python test_autoscript_poll.py
    python test_autoscript_poll.py --host 192.168.0.1 --port 7520
    python test_autoscript_poll.py --save-log poll.txt
    python test_autoscript_poll.py --verbose        # tracebacks for FAILs

Run it with the fibsemOS env activated.

Reading the result
    PASS  the property was read.
    SKIP  the instrument does not have that hardware or the client does not
          offer that call: no manipulator, no plasma source, a detector with
          no brightness/contrast (e.g. "External"), or a call added in a later
          AutoScript. Expected on most instruments.
    FAIL  anything else. Worth a look with --verbose.

Detector brightness/contrast read from whichever detector is active in xT. If
both beams show SKIP there, both are probably set to a detector without those
controls; select ETD (or similar) for the electron beam in xT and re-run.
"""

import argparse
import re
import sys
import traceback
from datetime import datetime

import _common as c

# Server messages that mean "not present on this instrument / in this version".
# The wording changed between AutoScript releases, so several are listed.
EXPECTED_ABSENCE = (
    "not installed on this microscope",           # manipulator and other devices
    "does not have a plasma FIB",                 # gallium-source instruments
    "doesn't have a brightness parameter",        # detector, older wording
    "doesn't have a contrast parameter",          # detector, older wording
    "method or operation is not implemented",     # detector etc., newer wording
)

results = {"pass": 0, "skip": 0, "fail": 0}
VERBOSE = False


def line(tag, colour, name, text):
    print(f"  {colour}{tag}{c.RESET}  {name:<52} {text}")


def poll(name, read, skip_if_none=False):
    try:
        value = read()
    except (NotImplementedError, AttributeError) as e:
        line("SKIP", c.YELLOW, name, f"{type(e).__name__}: {e}"); results["skip"] += 1
        return
    except Exception as e:  # noqa: BLE001 - every failure is reported, none raised
        msg = " ".join(str(e).split())
        if any(s in msg for s in EXPECTED_ABSENCE):
            line("SKIP", c.YELLOW, name, msg); results["skip"] += 1
        else:
            line("FAIL", c.RED, name, f"{type(e).__name__}: {msg}"); results["fail"] += 1
            if VERBOSE:
                traceback.print_exc()
        return
    if value is None and skip_if_none:
        line("SKIP", c.YELLOW, name, "returned None"); results["skip"] += 1
    else:
        line("PASS", c.GREEN, name, f"{c.CYAN}{value!r}{c.RESET}"); results["pass"] += 1


def section(title):
    print(f"\n{c.BOLD}-- {title} --{c.RESET}")


def run(host, port):
    try:
        from autoscript_sdb_microscope_client import SdbMicroscopeClient
    except ImportError as e:
        c.err(f"Cannot import the AutoScript client: {e}")
        c.info("Activate the fibsemOS env, or run install_autoscript_wheels.py.")
        sys.exit(1)

    print(f"\n{c.BOLD}AutoScript API poll{c.RESET}")
    print(f"  Run at : {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print(f"  Target : {host}:{port}")

    section("Connection")
    m = SdbMicroscopeClient()
    try:
        m.connect(host=host, port=port)
    except Exception as e:  # noqa: BLE001
        line("FAIL", c.RED, "connect", f"{type(e).__name__}: {e}"); results["fail"] += 1
        summary()
        return
    line("PASS", c.GREEN, "connect", f"{host}:{port}"); results["pass"] += 1

    section("System")
    poll("service.system.name", lambda: m.service.system.name)
    poll("service.system.serial_number", lambda: m.service.system.serial_number)
    poll("service.system.version", lambda: m.service.system.version)
    poll("service.autoscript.client.version", lambda: m.service.autoscript.client.version)
    poll("service.autoscript.server.version", lambda: m.service.autoscript.server.version)

    section("Vacuum")
    poll("vacuum.chamber_state", lambda: m.vacuum.chamber_state)
    poll("vacuum.chamber_pressure.value", lambda: m.vacuum.chamber_pressure.value)

    section("Stage")
    poll("specimen.stage.is_installed", lambda: m.specimen.stage.is_installed)
    poll("specimen.compustage.is_installed", lambda: m.specimen.compustage.is_installed)
    try:
        compu = m.specimen.compustage.is_installed
    except Exception:  # noqa: BLE001
        compu = False
    stage, label = (m.specimen.compustage, "compustage") if compu else (m.specimen.stage, "stage")
    poll(f"{label}.current_position", lambda: stage.current_position)
    poll(f"{label}.is_homed", lambda: stage.is_homed)
    poll(f"{label}.is_linked", lambda: stage.is_linked)

    for beam_label, beam in (("electron_beam", m.beams.electron_beam),
                             ("ion_beam", m.beams.ion_beam)):
        section(beam_label.replace("_", " ").title())
        poll(f"{beam_label}.is_on", lambda: beam.is_on)
        poll(f"{beam_label}.is_blanked", lambda: beam.is_blanked, skip_if_none=True)
        poll(f"{beam_label}.high_voltage.value", lambda: beam.high_voltage.value)
        poll(f"{beam_label}.high_voltage.limits", lambda: beam.high_voltage.limits)
        poll(f"{beam_label}.beam_current.value", lambda: beam.beam_current.value)
        if beam_label == "electron_beam":
            poll(f"{beam_label}.beam_current.limits", lambda: beam.beam_current.limits)
        else:
            poll(f"{beam_label}.beam_current.available_values",
                 lambda: beam.beam_current.available_values)
        poll(f"{beam_label}.horizontal_field_width.value",
             lambda: beam.horizontal_field_width.value)
        poll(f"{beam_label}.working_distance.value", lambda: beam.working_distance.value)
        poll(f"{beam_label}.scanning.resolution.value", lambda: beam.scanning.resolution.value)
        poll(f"{beam_label}.scanning.dwell_time.value", lambda: beam.scanning.dwell_time.value)
        poll(f"{beam_label}.scanning.rotation.value", lambda: beam.scanning.rotation.value)
        poll(f"{beam_label}.beam_shift.value", lambda: beam.beam_shift.value)
        poll(f"{beam_label}.stigmator.value", lambda: beam.stigmator.value)
        if beam_label == "electron_beam":
            poll(f"{beam_label}.beam_shift.limits", lambda: beam.beam_shift.limits)
            poll(f"{beam_label}.angular_correction.angle.value",
                 lambda: beam.angular_correction.angle.value)
        else:
            poll(f"{beam_label}.source.plasma_gas.value", lambda: beam.source.plasma_gas.value)
            poll(f"{beam_label}.source.plasma_gas.available_values",
                 lambda: beam.source.plasma_gas.available_values)

    section("Detectors (active detector per beam)")
    try:
        from autoscript_sdb_microscope_client.enumerations import ImagingDevice
        devices = (("electron", ImagingDevice.ELECTRON_BEAM), ("ion", ImagingDevice.ION_BEAM))
    except ImportError:
        devices = (("electron", None), ("ion", None))
    for label, device in devices:
        if device is not None:
            try:
                m.imaging.set_active_device(device)  # selects the view only; changes no beam
            except Exception:  # noqa: BLE001
                pass
        for prop in ("type", "mode", "brightness", "contrast"):
            poll(f"detector.{prop}.value [{label}]",
                 lambda prop=prop: getattr(m.detector, prop).value)
        for prop in ("type", "mode"):
            poll(f"detector.{prop}.available_values [{label}]",
                 lambda prop=prop: getattr(m.detector, prop).available_values)

    section("Imaging")
    poll("imaging.get_active_view()", lambda: m.imaging.get_active_view())
    poll("imaging.get_active_device()", lambda: m.imaging.get_active_device())

    section("Patterning")
    poll("patterning.state", lambda: m.patterning.state)
    poll("patterning.list_all_application_files()",
         lambda: m.patterning.list_all_application_files())

    section("Gas injection")
    poll("gas.list_all_gis_ports()", lambda: m.gas.list_all_gis_ports())
    poll("gas.list_all_multichem_ports()", lambda: m.gas.list_all_multichem_ports())

    section("Manipulator")
    poll("specimen.manipulator.state", lambda: m.specimen.manipulator.state)
    poll("specimen.manipulator.current_position",
         lambda: m.specimen.manipulator.current_position)

    try:
        m.disconnect()
    except Exception:  # noqa: BLE001
        pass
    summary()


def summary():
    p, s, f = results["pass"], results["skip"], results["fail"]
    print(f"\n{c.BOLD}-- Summary --{c.RESET}")
    print(f"  {c.GREEN}{p} passed{c.RESET} | {c.YELLOW}{s} skipped{c.RESET} | "
          f"{c.RED}{f} failed{c.RESET}  (of {p + s + f})")
    if f:
        print(f"  {c.RED}{f} unexpected failure(s); re-run with --verbose.{c.RESET}")
    else:
        print(f"  {c.GREEN}No unexpected failures.{c.RESET}")


class _Tee:
    """Writes to the console as is and to a log file without colour codes."""
    _ANSI = re.compile(r"\x1b\[[0-9;]*m")

    def __init__(self, console, logfile):
        self.console, self.logfile = console, logfile

    def write(self, s):
        self.console.write(s)
        self.logfile.write(self._ANSI.sub("", s))

    def flush(self):
        self.console.flush()
        self.logfile.flush()


def main():
    global VERBOSE
    cfg = c.load_config()
    p = argparse.ArgumentParser(description="Read-only AutoScript API poll.")
    p.add_argument("--host", default=cfg["mpc"]["host"])
    p.add_argument("--port", type=int, default=cfg["mpc"]["port"])
    p.add_argument("--verbose", action="store_true", help="tracebacks for FAILs")
    p.add_argument("--save-log", metavar="FILE", help="also write the output to FILE")
    args = p.parse_args()
    VERBOSE = args.verbose

    if args.save_log:
        logfile = open(args.save_log, "w", encoding="utf-8")
        sys.stdout = _Tee(sys.stdout, logfile)
    run(args.host, args.port)
    sys.exit(1 if results["fail"] else 0)


if __name__ == "__main__":
    main()
