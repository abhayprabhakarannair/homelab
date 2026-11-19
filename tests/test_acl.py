from itertools import product
from pathlib import Path

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
VARS = yaml.safe_load((ROOT / "group_vars/all/main.yml").read_text())
DEVICES = VARS["mqtt"]["devices"]
UI = VARS["mqtt"]["ui"]
TOPIC_ROOT = VARS["topic_root"]
DEVICE_LEAVES = ["meta", "status", "state", "event"]
LEAVES = [*DEVICE_LEAVES, "cmd"]


def render_acl():
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    return env.from_string((ROOT / "roles/mqtt/templates/acl.j2").read_text()).render(**VARS)


def parse(acl):
    """Return (patterns, per_user) as lists of (access, filter), following mosquitto's acl_file grammar."""
    patterns, per_user, user = [], {}, None
    for raw in acl.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, rest = line.partition(" ")
        if keyword == "user":
            user = rest.strip()
            per_user.setdefault(user, [])
            continue
        access, _, topic = rest.strip().partition(" ")
        if access not in ("read", "write", "readwrite", "deny"):
            access, topic = "readwrite", rest.strip()
        rule = (access, topic.strip())
        if keyword == "pattern":
            patterns.append(rule)
        elif keyword == "topic":
            assert user is not None, f"topic rule before any user: {line!r}"
            per_user[user].append(rule)
        else:
            raise AssertionError(f"unknown ACL keyword: {line!r}")
    return patterns, per_user


def matches(topic_filter, topic):
    f, t = topic_filter.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t) or (part != "+" and part != t[i]):
            return False
    return len(f) == len(t)


def allowed(rules, user, access, topic):
    patterns, per_user = rules
    effective = [(a, f.replace("%u", user)) for a, f in patterns] + per_user.get(user, [])
    hits = [a for a, f in effective if matches(f, topic)]
    return "deny" not in hits and any(a in (access, "readwrite") for a in hits)


@pytest.fixture(scope="module")
def rules():
    return parse(render_acl())


@pytest.mark.parametrize(
    ("filt", "topic", "expected"),
    [
        ("home/imp/cmd", "home/imp/cmd", True),
        ("home/+/cmd", "home/devil/cmd", True),
        ("home/+/cmd", "home/devil/cmd/x", False),
        ("home/#", "home/devil/state", True),
        ("home/#", "home", True),
        ("home/imp/cmd", "home/imp", False),
        ("home/imp", "home/imp/cmd", False),
    ],
)
def test_matches(filt, topic, expected):
    assert matches(filt, topic) is expected


@pytest.mark.parametrize(("device", "leaf"), list(product(DEVICES, DEVICE_LEAVES)))
def test_device_writes_own_state_topics(rules, device, leaf):
    topic = f"{TOPIC_ROOT}/{device}/{leaf}"
    assert allowed(rules, device, "write", topic)
    assert not allowed(rules, device, "read", topic)


@pytest.mark.parametrize("device", DEVICES)
def test_device_reads_but_cannot_forge_its_commands(rules, device):
    topic = f"{TOPIC_ROOT}/{device}/cmd"
    assert allowed(rules, device, "read", topic)
    assert not allowed(rules, device, "write", topic)


@pytest.mark.parametrize(
    ("device", "other", "leaf", "access"),
    [
        (d, o, leaf, a)
        for d, o in product(DEVICES, DEVICES + UI)
        if d != o
        for leaf in LEAVES
        for a in ("read", "write")
    ],
)
def test_device_isolated_from_other_clients(rules, device, other, leaf, access):
    assert not allowed(rules, device, access, f"{TOPIC_ROOT}/{other}/{leaf}")


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("topic", ["{root}/{d}", "{root}/{d}/cmd/x", "{root}/{d}/other", "other/{d}/state", "#"])
def test_device_has_nothing_outside_its_leaves(rules, device, topic):
    t = topic.format(root=TOPIC_ROOT, d=device)
    assert not allowed(rules, device, "read", t)
    assert not allowed(rules, device, "write", t)


@pytest.mark.parametrize(("ui", "target", "leaf"), list(product(UI, DEVICES, LEAVES)))
def test_ui_reads_everything_and_writes_only_commands(rules, ui, target, leaf):
    topic = f"{TOPIC_ROOT}/{target}/{leaf}"
    assert allowed(rules, ui, "read", topic)
    assert allowed(rules, ui, "write", topic) is (leaf == "cmd")


@pytest.mark.parametrize("ui", UI)
def test_ui_cannot_write_outside_the_root(rules, ui):
    assert not allowed(rules, ui, "write", f"other/{DEVICES[0]}/cmd")


def test_unknown_user_gets_only_its_own_pattern_topics(rules):
    assert not allowed(rules, "stranger", "read", f"{TOPIC_ROOT}/{DEVICES[0]}/state")
    assert allowed(rules, "stranger", "write", f"{TOPIC_ROOT}/stranger/state")
