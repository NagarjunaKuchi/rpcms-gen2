"""Guard: the openg2p-registry (registry-platform) version must be identical wherever it is pinned:
deploy/.env and `ARG RP_VERSION=` in every docker/*/Dockerfile. Stdlib + pytest only."""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent


def _pins():
    pins = {}
    env = re.search(r"^RP_VERSION=(\S+)", (REPO / "deploy/.env").read_text(), re.M)
    assert env, "deploy/.env has no RP_VERSION"
    pins["deploy/.env"] = env.group(1)
    for f in sorted((REPO / "docker").glob("*/Dockerfile")):
        m = re.search(r"^ARG RP_VERSION=(\S+)", f.read_text(), re.M)
        if m:
            pins[f.relative_to(REPO).as_posix()] = m.group(1)
    return pins


def test_pin_is_identical_everywhere():
    pins = _pins()
    assert len(pins) > 1, f"expected Dockerfile pins, found {pins}"
    assert len(set(pins.values())) == 1, f"RP_VERSION differs: {pins}"
