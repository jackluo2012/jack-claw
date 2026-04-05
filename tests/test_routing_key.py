"""routing_key 测试"""

import pytest
from jackclaw.feishu.session_key import parse_routing_key, build_routing_key, RoutingType


def test_parse_p2p():
    routing = parse_routing_key("p2p:ou_abc123")
    assert routing.type == RoutingType.P2P
    assert routing.open_id == "ou_abc123"


def test_parse_group():
    routing = parse_routing_key("group:oc_xyz789")
    assert routing.type == RoutingType.GROUP
    assert routing.chat_id == "oc_xyz789"


def test_parse_thread():
    routing = parse_routing_key("thread:oc_chat:ot_thread")
    assert routing.type == RoutingType.THREAD
    assert routing.root_id == "ot_thread"


def test_build_routing_key():
    assert build_routing_key(RoutingType.P2P, open_id="ou_test") == "p2p:ou_test"
    assert build_routing_key(RoutingType.GROUP, chat_id="oc_test") == "group:oc_test"
    assert build_routing_key(RoutingType.THREAD, chat_id="oc_chat", thread_id="ot_thread") == "thread:oc_chat:ot_thread"
