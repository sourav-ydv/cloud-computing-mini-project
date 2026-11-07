import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from nacl_sim import decide, load_rules


def test_blocked_range_denied_even_on_web_port():
    rules = load_rules(os.path.join(os.path.dirname(__file__), "..", "network", "nacl.json"))
    pkt = {"direction": "inbound", "protocol": "tcp", "port": 443, "address": "198.51.100.9"}
    action, _rule = decide(rules, pkt)
    assert action == "deny"


def test_ssh_allowed_only_from_management():
    rules = load_rules(os.path.join(os.path.dirname(__file__), "..", "network", "nacl.json"))
    pkt = {"direction": "inbound", "protocol": "tcp", "port": 22, "address": "10.20.5.140"}
    action, _rule = decide(rules, pkt)
    assert action == "allow"
