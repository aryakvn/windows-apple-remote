"""End-to-end: pyatv's own Companion client pairs with our server and presses buttons."""

import asyncio
from ipaddress import IPv4Address

import pyatv
from pyatv.conf import AppleTV, ManualService
from pyatv.const import Protocol

from atv_remote.server import Identity, RemoteServer


async def start(tmp_path, actions, pins):
    identity = Identity(tmp_path / "state.json")
    loop = asyncio.get_running_loop()
    server = await loop.create_server(
        lambda: RemoteServer(identity, "Test PC", actions.append, pins.append), "127.0.0.1", 0
    )
    return server, identity, server.sockets[0].getsockname()[1]


def config(identity, port, credentials=None):
    conf = AppleTV(IPv4Address("127.0.0.1"), "Test PC")
    conf.add_service(
        ManualService(identity.id, Protocol.Companion, port, {}, credentials=credentials)
    )
    return conf


async def pair(identity, port, pins):
    pairing = await pyatv.pair(config(identity, port), Protocol.Companion, asyncio.get_running_loop())
    await pairing.begin()
    pairing.pin(pins[-1])
    await pairing.finish()
    await pairing.close()
    assert pairing.has_paired
    return pairing.service.credentials


async def test_pair_and_control(tmp_path):
    actions, pins = [], []
    server, identity, port = await start(tmp_path, actions, pins)
    credentials = await pair(identity, port, pins)
    assert len(identity.clients) == 1
    assert len(Identity(tmp_path / "state.json").clients) == 1  # persisted

    atv = await pyatv.connect(config(identity, port, credentials), asyncio.get_running_loop())
    try:
        await atv.remote_control.play_pause()
        await atv.remote_control.volume_up()
        await atv.remote_control.next()
        await atv.remote_control.left()
        await atv.remote_control.select()
    finally:
        atv.close()
        server.close()

    assert actions == ["play_pause", "volume_up", "next", "left", "select"]


async def test_wrong_pin_is_rejected(tmp_path):
    actions, pins = [], []
    server, identity, port = await start(tmp_path, actions, pins)
    pairing = await pyatv.pair(config(identity, port), Protocol.Companion, asyncio.get_running_loop())
    await pairing.begin()
    pairing.pin((int(pins[-1]) + 1) % 10000)
    try:
        await pairing.finish()
    except Exception:
        pass
    await pairing.close()
    server.close()
    assert identity.clients == {}


async def test_unpaired_device_cannot_control(tmp_path):
    actions, pins = [], []
    server, identity, port = await start(tmp_path, actions, pins)
    credentials = await pair(identity, port, pins)
    identity.clients.clear()  # server forgets the device

    try:
        atv = await pyatv.connect(config(identity, port, credentials), asyncio.get_running_loop())
        await atv.remote_control.play_pause()
        atv.close()
    except Exception:
        pass
    server.close()
    assert actions == []


def test_opack_references_after_empty_string():
    # Shape of iOS 27's _systemInfo: an '' before a repeated key.
    from pyatv.support import opack

    from atv_remote.server import unpack_opack

    message = {"_c": {"m": "", "_idsCID": "abc", "_i": "58b4", "n": 128}, "_i": "_systemInfo", "f": 128.0}
    data = opack.pack(message)
    assert opack.unpack(data)[0] != message  # pyatv's decoder gets this wrong
    assert unpack_opack(data) == message


class _Transport:
    def __init__(self):
        self.messages = []

    def get_extra_info(self, key):
        return ("127.0.0.1", 49152)

    def write(self, data):
        from atv_remote.server import unpack_opack

        self.messages.append(unpack_opack(data[4:]))


def test_ios_remote_session_gets_answers(tmp_path):
    # Request sequence the iOS 27 Apple TV Remote sends after pair-verify.
    server = RemoteServer(Identity(tmp_path / "state.json"), "Test PC", print, print)
    server.transport = transport = _Transport()
    requests = [
        ("_systemInfo", {"name": "iPhone"}),
        ("_sessionStart", {"_sid": 1, "_srvT": "com.apple.tvremoteservices"}),
        ("TVRCSessionStart", {"ProtocolVersionKey": "1.2"}),
        ("FetchAttentionState", {}),
        ("FetchSiriRemoteInfo", {}),
        ("FetchSupportedActionsEvent", {}),
        ("FetchCurrentNowPlayingInfoEvent", {}),
        ("FetchCurrentTopShelfItemsEvent", {}),
        ("FetchMediaControlStatus", {}),
        ("_touchStart", {"_height": 1000.0, "_tFl": 0, "_width": 1000.0}),
        ("_tiStart", {}),
    ]
    for xid, (ident, content) in enumerate(requests):
        server._handle_message({"_i": ident, "_t": 2, "_c": content, "_x": xid})

    replies = {m["_x"]: m for m in transport.messages if m.get("_t") == 3}
    assert all("_ec" not in reply for reply in replies.values())
    assert set(replies) == set(range(len(requests)))
    info = replies[0]["_c"]
    assert info["_lP"] == 49152 and "com.apple.tvremoteservices" in info["_stA"]
    assert replies[9]["_c"] == {"_i": 1}
    assert replies[8]["_c"]["MediaControlFlags"]
