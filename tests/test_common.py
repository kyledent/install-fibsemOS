import json
import subprocess
from types import SimpleNamespace

import pytest

import _common as c


# ---- configuration -------------------------------------------------------------
def test_defaults_without_config(tmp_path):
    cfg = c.load_config(tmp_path / "missing.json")
    assert cfg == c.DEFAULTS
    assert cfg is not c.DEFAULTS


def test_config_overrides_nested_keys_only(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mpc": {"host": "10.0.0.5"}, "env_name": "x"}))
    cfg = c.load_config(path)
    assert cfg["mpc"]["host"] == "10.0.0.5"
    assert cfg["mpc"]["port"] == c.DEFAULTS["mpc"]["port"]  # untouched sibling
    assert cfg["env_name"] == "x"
    assert c.DEFAULTS["mpc"]["host"] == "192.168.0.1"        # defaults not mutated


def test_example_config_matches_defaults():
    example = json.loads((c.REPO_DIR / "config.example.json").read_text())
    assert example == c.DEFAULTS


def test_resolve_share():
    cfg = c.load_config(c.REPO_DIR / "no-such-file.json")
    assert c.resolve_share(cfg, "10.1.2.3") == (
        r"\\10.1.2.3\C$\Program Files\Thermo Scientific AutoScript\PythonPackages")
    assert c.resolve_share(cfg).startswith(r"\\192.168.0.1\C$")


# ---- wheels --------------------------------------------------------------------
def _touch(folder, *names):
    for name in names:
        (folder / name).write_bytes(b"")


def test_client_is_not_confused_with_client_tests(tmp_path):
    _touch(tmp_path, "autoscript_sdb_microscope_client_tests-4.9.0-py3-none-any.whl")
    assert c.find_wheel(tmp_path, "autoscript_sdb_microscope_client") is None
    _touch(tmp_path, "autoscript_sdb_microscope_client-4.9.0-py3-none-any.whl")
    assert c.find_wheel(tmp_path, "autoscript_sdb_microscope_client").name.startswith(
        "autoscript_sdb_microscope_client-4.9.0")


def test_newest_version_wins_numerically(tmp_path):
    _touch(tmp_path,
           "autoscript_core-5.9.0-py3-none-any.whl",
           "autoscript_core-5.21.0-py3-none-any.whl",
           "autoscript_core-5.12.0-py3-none-any.whl")
    assert c.find_wheel(tmp_path, "autoscript_core").name == "autoscript_core-5.21.0-py3-none-any.whl"


def test_collect_wheels_reports_missing_required(tmp_path):
    _touch(tmp_path,
           "autoscript_sdb_microscope_client-4.9.0-py3-none-any.whl",
           "autoscript_toolkit-4.9.0-py3-none-any.whl")
    wheels, missing = c.collect_wheels(tmp_path)
    assert missing == ["autoscript_core", "thermoscientific_logging"]
    assert {w.name.split("-")[0] for w in wheels} == {
        "autoscript_sdb_microscope_client", "autoscript_toolkit"}


def test_collect_wheels_without_optional(tmp_path):
    _touch(tmp_path, *(f"{p}-1.0.0-py3-none-any.whl"
                       for p in c.REQUIRED_WHEELS + c.OPTIONAL_WHEELS))
    wheels, missing = c.collect_wheels(tmp_path, include_optional=False)
    assert not missing
    assert len(wheels) == len(c.REQUIRED_WHEELS)


def test_install_wheels_unreachable_folder(tmp_path, capsys):
    assert c.install_wheels("conda", "env", tmp_path / "nope") is False
    assert "not reachable" in capsys.readouterr().out


# ---- conda discovery -----------------------------------------------------------
def test_windows_prefers_exe_over_bat(monkeypatch):
    found = {"conda.exe": r"C:\mf\Scripts\conda.exe", "conda": r"C:\mf\condabin\conda.bat"}
    monkeypatch.setattr(c.sys, "platform", "win32")
    monkeypatch.setattr(c.shutil, "which", lambda name: found.get(name))
    assert c.conda_cmd() == r"C:\mf\Scripts\conda.exe"


def test_mamba_preferred_and_full_path_returned(monkeypatch):
    found = {"mamba": "/opt/mf/bin/mamba", "conda": "/opt/mf/bin/conda"}
    monkeypatch.setattr(c.sys, "platform", "linux")
    monkeypatch.setattr(c.shutil, "which", lambda name: found.get(name))
    assert c.conda_cmd() == "/opt/mf/bin/mamba"


def test_conda_run_starts_env_executable_directly(monkeypatch, tmp_path):
    # Not `conda run`: the env's own python, with the env's PATH, args as given.
    prefix = tmp_path / "envs" / "fibsem-os"
    bindir = prefix / ("Scripts" if c.sys.platform == "win32" else "bin")
    bindir.mkdir(parents=True)
    monkeypatch.setattr(c, "list_env_prefixes", lambda conda: [tmp_path, prefix])
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw["env"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(c.subprocess, "run", fake_run)
    monkeypatch.setattr(c.shutil, "which",
                        lambda name, path=None: str(bindir / name) if path else None)

    code = "a = 1\nprint(a % 2, '&', \"^\")"
    c.conda_run("conda", "fibsem-os", ["python", "-c", code], capture=True)
    assert seen["cmd"] == [str(bindir / "python"), "-c", code]  # multi-line code intact
    assert seen["env"]["CONDA_PREFIX"] == str(prefix)
    assert seen["env"]["PATH"].split(c.os.pathsep)[0] == str(
        prefix if c.sys.platform == "win32" else prefix / "bin")


def test_conda_run_unknown_env_exits(monkeypatch):
    monkeypatch.setattr(c, "list_env_prefixes", lambda conda: [])
    with pytest.raises(SystemExit):
        c.conda_run("conda", "nope", ["python", "-V"])


@pytest.mark.parametrize("platform, first", [("win32", ""), ("linux", "bin")])
def test_env_environ_puts_env_tools_first(monkeypatch, tmp_path, platform, first):
    monkeypatch.setattr(c.sys, "platform", platform)
    monkeypatch.setenv("PYTHONHOME", "/elsewhere")
    environ = c.env_environ(tmp_path / "e")
    assert environ["PATH"].split(c.os.pathsep)[0] == str(tmp_path / "e" / first).rstrip("/\\")
    assert "PYTHONHOME" not in environ
    if platform == "win32":
        assert str(tmp_path / "e" / "Library" / "bin") in environ["PATH"]


def test_list_envs_reads_json(monkeypatch):
    payload = json.dumps({"envs": ["/mf", "/mf/envs/fibsem-os", r"C:\mf\envs\other"]})
    monkeypatch.setattr(c.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout=payload, stderr="", returncode=0))
    names = c.list_conda_envs("conda")
    assert "fibsem-os" in names
    assert c.conda_env_exists("conda", "fibsem-os")


def test_list_envs_survives_failure(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("conda", 60)
    monkeypatch.setattr(c.subprocess, "run", boom)
    assert c.list_conda_envs("conda") == []


@pytest.mark.parametrize("value, expected", [("fibsem-os", "fibsem-os"), ("base", None), (None, None)])
def test_active_env_ignores_base(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
    else:
        monkeypatch.setenv("CONDA_DEFAULT_ENV", value)
    assert c.active_env() == expected


def test_save_host_keeps_other_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"env_name": "mine", "mpc": {"port": 7521}}))
    c.save_host("10.0.0.9", path)
    data = json.loads(path.read_text())
    assert data == {"env_name": "mine", "mpc": {"port": 7521, "host": "10.0.0.9"}}


def test_save_host_creates_config(tmp_path):
    path = tmp_path / "config.json"
    c.save_host("10.0.0.9", path)
    assert c.load_config(path)["mpc"]["host"] == "10.0.0.9"


def test_conda_found_beside_interpreter_when_not_on_path(monkeypatch, tmp_path):
    # A fresh Miniforge run through its own python.exe, PATH untouched.
    (tmp_path / "Scripts").mkdir()
    (tmp_path / "Scripts" / "conda.exe").write_bytes(b"")
    monkeypatch.setattr(c.sys, "platform", "win32")
    monkeypatch.setattr(c.sys, "prefix", str(tmp_path))
    monkeypatch.setattr(c.shutil, "which", lambda name: None)
    monkeypatch.delenv("CONDA_EXE", raising=False)
    assert c.conda_cmd() == str(tmp_path / "Scripts" / "conda.exe")


def test_conda_exe_env_var_is_last_resort(monkeypatch, tmp_path):
    exe = tmp_path / "conda"
    exe.write_bytes(b"")
    monkeypatch.setattr(c.sys, "prefix", str(tmp_path / "elsewhere"))
    monkeypatch.setattr(c.shutil, "which", lambda name: None)
    monkeypatch.setenv("CONDA_EXE", str(exe))
    assert c.conda_cmd() == str(exe)
    monkeypatch.delenv("CONDA_EXE")
    assert c.conda_cmd() is None
