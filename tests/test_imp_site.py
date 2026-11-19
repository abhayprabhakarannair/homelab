import re
import shutil
import subprocess
from pathlib import Path

import jinja2
import pytest
from c import c_string

ROOT = Path(__file__).resolve().parents[1]

CONSUMER = r"""
#include <array>
#include <cstdint>
#include "site.h"
using Mac = std::array<std::uint8_t, 6>;
struct TargetConfig { const char* name; Mac mac; std::uint8_t ip[4]; };
constexpr TargetConfig kTargets[] = IMP_TARGETS;
static_assert(sizeof(kTargets) / sizeof(kTargets[0]) == EXPECTED_TARGETS);
int main() {
  const char* values[] = {IMP_WIFI_SSID, IMP_WIFI_PASS, IMP_MQTT_URI, IMP_MQTT_USER, IMP_MQTT_PASS, IMP_OTA_PASS,
                          IMP_TOPIC};
  return values[0] == nullptr;
}
"""

DEVIL = {"devil": {"mac": "02:00:00:00:00:01", "ip": "192.0.2.10"}}


def render(wifi_password="p@ss", ssid="home", targets=None):
    targets = targets or DEVIL
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, trim_blocks=True, keep_trailing_newline=True)
    env.filters["c_string"] = c_string
    env.filters["regex_replace"] = lambda value, pattern, repl: re.sub(pattern, repl, value)
    template = env.from_string((ROOT / "playbooks/templates/imp-site.h.j2").read_text())
    return template.render(
        secrets={"wifi": {"ssid": ssid, "password": wifi_password}, "mqtt": {"imp": "m"}, "imp_ota": "o"},
        mqtt={"funnel_host": "bus.example", "funnel_port": 8443},
        topic_root="home",
        imp={"wakes": list(targets)},
        hostvars={name: {"wol": wol} for name, wol in targets.items()},
    )


@pytest.fixture(scope="session")
def cxx():
    compiler = shutil.which("g++") or shutil.which("clang++")
    assert compiler, "a C++ compiler is required"
    return compiler


def build(cxx, tmp_path, header, expected_targets):
    (tmp_path / "site.h").write_text(header)
    (tmp_path / "consumer.cpp").write_text(CONSUMER)
    subprocess.run(
        [
            cxx,
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsyntax-only",
            f"-DEXPECTED_TARGETS={expected_targets}",
            "-I",
            str(tmp_path),
            str(tmp_path / "consumer.cpp"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def run_probe(cxx, tmp_path, macro):
    probe = tmp_path / "probe.cpp"
    probe.write_text(f'#include "site.h"\n#include <cstdio>\nint main() {{ std::fputs({macro}, stdout); }}\n')
    exe = tmp_path / "probe"
    subprocess.run([cxx, "-std=c++17", "-I", str(tmp_path), str(probe), "-o", str(exe)], check=True)
    return subprocess.run([str(exe)], check=True, capture_output=True).stdout


def test_single_target_values(cxx, tmp_path):
    header = render()
    assert '#define IMP_MQTT_URI "mqtts://bus.example:8443"' in header
    assert '#define IMP_TOPIC "home/imp"' in header
    assert '{"devil", { 0x02, 0x00, 0x00, 0x00, 0x00, 0x01 }, { 192, 0, 2, 10 }}' in header
    build(cxx, tmp_path, header, 1)


def test_multiple_targets(cxx, tmp_path):
    targets = {**DEVIL, "homelab-one": {"mac": "aa:bb:cc:dd:ee:ff", "ip": "10.0.0.2"}}
    build(cxx, tmp_path, render(targets=targets), 2)


@pytest.mark.parametrize(
    "value",
    [
        'quote"inside',
        "back\\slash",
        "trailing\\",
        "spaces and !@#$%^&*()",
        "ünïcødé",
        "emoji 😀🔐",
        "trigraph ??= ??/",
        "hex-looking \\x41 then F",
        "tab\tand\nnewline",
        "{{braces}}",
    ],
)
def test_awkward_credentials_round_trip(cxx, tmp_path, value):
    build(cxx, tmp_path, render(wifi_password=value, ssid=value), 1)
    assert run_probe(cxx, tmp_path, "IMP_WIFI_PASS") == value.encode()
    assert run_probe(cxx, tmp_path, "IMP_WIFI_SSID") == value.encode()


def test_template_is_deterministic():
    assert render() == render()
