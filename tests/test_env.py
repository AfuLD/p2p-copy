import os
import re
import sys
import shutil
from pathlib import Path
from importlib import metadata as md

# Defaults (used if pyproject.toml can't be read)
DEFAULT_REQUIRED = {"typer": "0.12", "websockets": "12.0", "rich": "13.7", "zstandard": "0.22"}
DEFAULT_EXTRAS = {"cryptography": "42.0", "argon2_cffi": "21.1"}

try:  # Python 3.11+
    # noinspection PyCompatibility
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # Python 3.10 fallback (no extra deps)
    tomllib = None  # Fall back to the DEFAULT_* above


def _parse_version(v: str):
    nums, cur = [], ""
    for ch in v:
        if ch.isdigit():
            cur += ch
        elif cur:
            nums.append(int(cur)); cur = ""
    if cur:
        nums.append(int(cur))
    return tuple(nums or [0])


def _version_ok(installed: str, minimum: str) -> bool:
    return _parse_version(installed) >= _parse_version(minimum)


def _split_name_and_spec(req: str):
    """Return (name, op, ver) for a simple requirement like
    'pkg>=1.2' or 'pkg==1.2' or just 'pkg'. Extras/markers are ignored.
    This intentionally supports only the operators we actually use here.
    """
    # Remove environment markers (e.g., "; python_version >= '3.10'")
    req = req.split(";", 1)[0].strip()
    # Strip extras: pkg[extra]
    req = re.sub(r"\[[^]]*]", "", req)

    op = None
    ver = None
    if ">=" in req:
        name, ver = req.split(">=", 1)
        op = ">="
    elif "==" in req:
        name, ver = req.split("==", 1)
        op = "=="
    else:
        name = req
    return name.strip(), op, (ver.strip() if ver else None)


def _load_requirements_from_pyproject():
    """Read REQUIRED and EXTRAS from pyproject.toml if possible.
    Returns (required: dict[str,str], extras: dict[str, str], dev: dict[str,str]).
    If tomllib isn't available or file missing, falls back to defaults.
    """
    root = Path(__file__).resolve().parents[1]
    pyproj = root / "pyproject.toml"
    if not (tomllib and pyproj.exists()):
        return dict(DEFAULT_REQUIRED), dict(DEFAULT_EXTRAS), {}

    with pyproj.open("rb") as f:
        data = tomllib.load(f)

    required: dict[str, str] = {}
    for req in data.get("project", {}).get("dependencies", []) or []:
        name, op, ver = _split_name_and_spec(req)
        if ver and op in {">=", "=="}:
            required[name] = ver
        else:
            # No version specified → treat as 0
            required[name] = "0"

    # Optional dependencies
    opt = data.get("project", {}).get("optional-dependencies", {}) or {}
    extras: dict[str, str] = {}
    for req in opt.get("compression", []) + opt.get("security", []):
        name, op, ver = _split_name_and_spec(req)
        if ver:
            extras[name] = ver
        else:
            extras[name] = "0"

    dev: dict[str, str] = {}
    for req in opt.get("dev", []):
        name, op, ver = _split_name_and_spec(req)
        if ver:
            dev[name] = ver
        else:
            dev[name] = "0"

    # If the file didn't specify the ones we expect, merge defaults
    for k, v in DEFAULT_REQUIRED.items():
        required.setdefault(k, v)
    for k, v in DEFAULT_EXTRAS.items():
        extras.setdefault(k, v)

    return required, extras, dev


REQUIRED, EXTRAS, DEV = _load_requirements_from_pyproject()


def test_virtualenv_active():
    in_venv = (sys.prefix != sys.base_prefix) or bool(os.environ.get("VIRTUAL_ENV"))
    assert in_venv, "Not in a virtualenv. Select your project venv in IDEA."
    expected = os.environ.get("P2P_COPY_EXPECTED_VENV")
    if expected:
        assert expected in sys.prefix, f"Expected venv fragment '{expected}', got '{sys.prefix}'"


def test_cli_in_venv_path():
    exe = shutil.which("p2p-copy")
    assert exe, "CLI 'p2p-copy' not found. Did you run: pip install -e . ?"
    assert sys.prefix in exe, f"'p2p-copy' not installed in active venv: {exe}"


def test_required_dependencies_present_and_versions():
    missing, wrong = [], []
    for pkg, min_v in REQUIRED.items():
        try:
            inst_v = md.version(pkg)
        except md.PackageNotFoundError:
            missing.append(pkg); continue
        if not _version_ok(inst_v, min_v):
            wrong.append((pkg, inst_v, min_v))
    assert not missing, f"Missing packages: {missing}. Run: pip install -e ."
    assert not wrong, "Version too low: " + ", ".join(f"{p} {v} < {m}" for p, v, m in wrong)


def test_optional_extras():
    missing, wrong = [], []
    for pkg, min_v in EXTRAS.items():
        try:
            inst_v = md.version(pkg)
        except md.PackageNotFoundError:
            missing.append(pkg); continue
        if not _version_ok(inst_v, min_v):
            wrong.append((pkg, inst_v, min_v))
    assert not missing, "Missing extras: " + ", ".join(missing)
    assert not wrong, "Extra version too low: " + ", ".join(f"{p} {v} < {m}" for p, v, m in wrong)


def test_dev_extras():
    missing, wrong = [], []
    for pkg, min_v in DEV.items():
        try:
            inst_v = md.version(pkg)
        except md.PackageNotFoundError:
            missing.append(pkg); continue
        # If pyproject pins ==, we still do a >= check here; adjust if you need strict equality
        if not _version_ok(inst_v, min_v):
            wrong.append((pkg, inst_v, min_v))
    assert not missing, "Missing dev extras: " + ", ".join(missing)
    assert not wrong, "Dev extra version too low: " + ", ".join(f"{p} {v} < {m}" for p, v, m in wrong)


def test_package_imports():
    import p2p_copy  # noqa: F401
