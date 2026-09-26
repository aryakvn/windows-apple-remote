"""Companion-protocol server that makes this PC show up in the Apple TV Remote app.

Pairing/crypto comes from pyatv's CompanionServerAuth. On top of it we add what a
real Apple TV does and pyatv's test server skips: a per-install key, a random PIN
per pairing, and rejecting devices that never paired.
"""

import asyncio
import binascii
import hashlib
import json
import logging
import secrets
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from pyatv.auth.hap_srp import hkdf_expand
from pyatv.auth.hap_tlv8 import ErrorCode, TlvValue, read_tlv, write_tlv
from pyatv.const import TouchAction
from pyatv.protocols.companion import MediaControlFlags
from pyatv.protocols.companion.api import HidCommand, MediaControlCommand
from pyatv.protocols.companion.connection import FrameType
from pyatv.protocols.companion.server_auth import (
    CompanionServerAuth,
    generate_keys,
    new_server_session,
)
from pyatv.support import chacha20, opack

_LOGGER = logging.getLogger(__name__)

AUTH_FRAMES = {FrameType.PS_Start, FrameType.PS_Next, FrameType.PV_Start, FrameType.PV_Next}
OPACK_FRAMES = AUTH_FRAMES | {FrameType.U_OPACK, FrameType.E_OPACK, FrameType.P_OPACK}
RESPONSE = 3  # "_t" value of a response
# Device facts taken from servers known to work with the iOS remote (see
# thiccaxe/CompanionGames); tvremoted drops the session when these look wrong.
MODEL = "AppleTV5,3"
SOURCE_VERSION = "715.2"
RP_FLAGS = "0xB6782"
SERVICE_TYPES = [
    "com.apple.tvremoteservices",  # the service the remote opens a session with
    "com.apple.bluetooth.remote",
    "com.apple.siri.wakeup",
    "com.apple.home.messaging",
    "com.apple.workflow.remotewidgets",
    "com.apple.devicediscoveryui.rapportwake",
]

# The remote is used as a media controller: directions and taps map to media keys,
# the same as touchpad swipes.
HID_ACTIONS = {
    HidCommand.Up: "volume_up",
    HidCommand.Down: "volume_down",
    HidCommand.Left: "previous",
    HidCommand.Right: "next",
    HidCommand.Select: "play_pause",  # a tap on the touch area arrives as Select
    HidCommand.Menu: "back",
    HidCommand.PlayPause: "play_pause",
    HidCommand.VolumeUp: "volume_up",
    HidCommand.VolumeDown: "volume_down",
}
# ponytail: Play and Pause both toggle; Windows has one play/pause key and we don't track player state
MCC_ACTIONS = {
    MediaControlCommand.Play: "play_pause",
    MediaControlCommand.Pause: "play_pause",
    MediaControlCommand.NextTrack: "next",
    MediaControlCommand.PreviousTrack: "previous",
}
MEDIA_FLAGS = (
    MediaControlFlags.Play
    | MediaControlFlags.Pause
    | MediaControlFlags.NextTrack
    | MediaControlFlags.PreviousTrack
    | MediaControlFlags.Volume  # lets the iPhone's volume buttons control the PC
)
SWIPE_FRACTION = 0.15  # swipe must cover this share of the touchpad to count
VOLUME_STEP_FRACTION = 0.1  # each extra 10% of vertical swipe = one more volume step
# iOS 27 sends drags as _tPh 2; pyatv's TouchAction only knows 3 (Hold).
TOUCH_DRAG = {2, TouchAction.Hold.value}
MOUSE_SPEED = 1.5  # cursor pixels per touchpad unit (the touchpad is 1000 units wide)


class _RefTable(list):
    """OPACK back-reference table matching Apple's encoder (and pyatv's own pack()).

    pyatv's decoder also tables 1-byte objects ('' and b'') and dedupes by ==, so a
    message containing '' resolves later references one slot off (seen with iOS 27's
    _systemInfo). Remove when pyatv's unpack is fixed.
    """

    def __contains__(self, value):
        return any(type(item) is type(value) and item == value for item in self)

    def append(self, value):
        if value not in ("", b""):
            super().append(value)


def unpack_opack(data):
    return opack._unpack(data, _RefTable())[0]  # pylint: disable=protected-access


class Identity:
    """Persistent server identity and paired devices, stored as JSON."""

    def __init__(self, path):
        self.path = Path(path)
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.id = data.get("id") or str(uuid.uuid4()).upper()
        self.seed = bytes.fromhex(data["seed"]) if "seed" in data else secrets.token_bytes(32)
        self.clients = data.get("clients", {})  # pairing id -> Ed25519 public key (hex)
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"id": self.id, "seed": self.seed.hex(), "clients": self.clients}
        self.path.write_text(json.dumps(data, indent=2))

    def txt_record(self):
        """mDNS TXT properties of an Apple TV, with stable ids derived from our seed."""
        digest = hashlib.sha256(self.seed).hexdigest()
        mac = ":".join(digest[i : i + 2] for i in range(48, 60, 2)).upper()
        return {
            "rpMac": "2",
            "rpFl": RP_FLAGS,
            "rpMd": MODEL,
            "rpVr": SOURCE_VERSION,
            "rpHN": digest[0:12],
            "rpHA": digest[12:24],
            "rpAD": digest[24:36],
            "rpHI": digest[36:48],
            "rpBA": mac,
            "rpMRtID": self.id,
        }

    def _uuid(self, label):
        return str(uuid.UUID(hashlib.sha256(self.seed + label).hexdigest()[:32])).upper()

    def system_info(self, name, port):
        """Our answer to the client's _systemInfo, mirroring the fields an Apple TV sends."""
        txt = self.txt_record()
        return {
            "name": name,
            "model": MODEL,
            "_sv": SOURCE_VERSION,
            "_i": txt["rpHI"],
            "_idsID": self._uuid(b"ids"),
            "_pubID": txt["rpBA"],
            "_mrID": self.id,
            "_mRtID": self.id,
            "_lP": port,
            "_stA": SERVICE_TYPES,
            "_sf": 65536,
            "_bf": 1920,
            "_cf": 512,
            "_clFl": 128,
            "_msSt": 1,
            "_msRo": 1,
            "_dCapF": 1,
            "_siriInfo": {
                "collectorElectionVersion": 1.0,
                "peerData": {
                    "productType": MODEL,
                    "userInterfaceIdiom": "ZEUS",  # Apple TV
                    "userAssignedDeviceName": name,
                    "assistantIdentifier": self._uuid(b"assistant"),
                    "sharedUserIdentifier": self._uuid(b"user"),
                    "isLocationSharingDevice": False,
                    "isSiriCloudSyncEnabled": False,
                },
                "audio-session-coordination.system-info": {
                    "isSupportedAndEnabled": False,
                    "mediaRemoteGroupIdentifier": self._uuid(b"group"),
                    "mediaRemoteRouteIdentifier": self.id,
                },
            },
        }


class RemoteServer(CompanionServerAuth, asyncio.Protocol):
    """One connection from an iOS device."""

    def __init__(self, identity, name, on_action, on_pin, on_move=None):
        super().__init__(name, unique_id=identity.id)
        self.keys = generate_keys(identity.seed)
        self.identity = identity
        self.on_action = on_action
        self.on_pin = on_pin
        self.on_move = on_move  # (dx, dy) in pixels; mouse mode needs it
        self.mouse_mode = False  # TV button toggles: touch area moves the cursor
        self.transport = None
        self.buffer = b""
        self.chacha = None
        self._client_verify_pub = None
        self._touchpad = (1000.0, 1000.0)
        self._touch_start = None
        self._mouse_rest = (0.0, 0.0)
        self._volume = 0.5  # what we last told the iPhone; SetVolume moves relative to it

    # asyncio.Protocol

    def connection_made(self, transport):
        self.transport = transport
        _LOGGER.info("Device connected: %s", transport.get_extra_info("peername"))

    def connection_lost(self, exc):
        _LOGGER.info("Device disconnected")
        self.transport = None

    def data_received(self, data):
        self.buffer += data
        while len(self.buffer) >= 4:
            end = 4 + int.from_bytes(self.buffer[1:4], "big")
            if len(self.buffer) < end:
                return
            header, payload = self.buffer[:4], self.buffer[4:end]
            self.buffer = self.buffer[end:]
            try:
                self._handle_frame(header, payload)
            except Exception:
                # A broken frame desyncs the cipher counters; drop the connection.
                _LOGGER.exception("Bad frame (type %d), closing connection", header[0])
                self.transport.close()
                return

    def _handle_frame(self, header, payload):
        frame_type = FrameType(header[0])
        if self.chacha and payload:
            payload = self.chacha.decrypt(payload, aad=header)
        if frame_type not in OPACK_FRAMES:
            _LOGGER.debug("Ignoring %s frame: %s", frame_type, payload.hex())
            return
        message = unpack_opack(payload) if payload else {}
        if frame_type in AUTH_FRAMES:
            self.handle_auth_frame(frame_type, message)
        elif frame_type == FrameType.E_OPACK and self.chacha:
            _LOGGER.debug("Received: %s", message)
            self._handle_message(message)
        else:
            _LOGGER.debug("Ignoring %s frame", frame_type)

    # CompanionServerAuth hooks

    def send_to_client(self, frame_type, data):
        payload = opack.pack(data)
        length = len(payload) + (16 if self.chacha else 0)
        header = bytes([frame_type.value]) + length.to_bytes(3, "big")
        if self.chacha:
            payload = self.chacha.encrypt(payload, aad=header)
        self.transport.write(header + payload)

    def enable_encryption(self, output_key, input_key):
        self.chacha = chacha20.Chacha20Cipher(output_key, input_key, nonce_length=12)

    def _m1_setup(self, pairing_data):
        pin = f"{secrets.randbelow(10000):04d}"
        self.session, self.salt = new_server_session(self.keys, pin)
        self.on_pin(pin)
        super()._m1_setup(pairing_data)

    def _m5_setup(self, pairing_data):
        srp_key = binascii.unhexlify(self.session.key)
        session_key = hkdf_expand("Pair-Setup-Encrypt-Salt", "Pair-Setup-Encrypt-Info", srp_key)
        cipher = chacha20.Chacha20Cipher(session_key, session_key)
        # Fails with InvalidTag unless the client knew the PIN.
        tlv = read_tlv(cipher.decrypt(pairing_data[TlvValue.EncryptedData], nonce=b"PS-Msg05"))
        client_id, client_ltpk = tlv[TlvValue.Identifier], tlv[TlvValue.PublicKey]
        ios_x = hkdf_expand(
            "Pair-Setup-Controller-Sign-Salt", "Pair-Setup-Controller-Sign-Info", srp_key
        )
        Ed25519PublicKey.from_public_bytes(client_ltpk).verify(
            tlv[TlvValue.Signature], ios_x + client_id + client_ltpk
        )

        acc_x = hkdf_expand("Pair-Setup-Accessory-Sign-Salt", "Pair-Setup-Accessory-Sign-Info", srp_key)
        info = {"name": self.device_name, "model": MODEL}
        reply = write_tlv(
            {
                TlvValue.Identifier: self.unique_id,
                TlvValue.PublicKey: self.keys.auth_pub,
                TlvValue.Signature: self.keys.sign.sign(acc_x + self.unique_id + self.keys.auth_pub),
                TlvValue.Name: opack.pack(info),
            }
        )
        encrypted = cipher.encrypt(reply, nonce=b"PS-Msg06")
        self.send_to_client(
            FrameType.PS_Next,
            {"_pd": write_tlv({TlvValue.SeqNo: b"\x06", TlvValue.EncryptedData: encrypted})},
        )

        self.identity.clients[client_id.decode()] = client_ltpk.hex()
        self.identity.save()
        _LOGGER.info("Paired with %s", client_id.decode())
        print("Paired. The device is remembered for next time.")
        # iOS keeps using this connection, encrypted with keys from the pairing secret.
        self.enable_encryption(
            hkdf_expand("", "ServerEncrypt-main", srp_key),
            hkdf_expand("", "ClientEncrypt-main", srp_key),
        )

    def _m1_verify(self, pairing_data):
        self._client_verify_pub = pairing_data[TlvValue.PublicKey]
        super()._m1_verify(pairing_data)

    def _m3_verify(self, pairing_data):
        # pyatv's server skips this check; without it any device could connect unpaired.
        shared = self.keys.verify.exchange(X25519PublicKey.from_public_bytes(self._client_verify_pub))
        session_key = hkdf_expand("Pair-Verify-Encrypt-Salt", "Pair-Verify-Encrypt-Info", shared)
        server_pub = self.keys.verify_pub.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        try:
            cipher = chacha20.Chacha20Cipher(session_key, session_key)
            tlv = read_tlv(cipher.decrypt(pairing_data[TlvValue.EncryptedData], nonce=b"PV-Msg03"))
            client_id = tlv[TlvValue.Identifier]
            ltpk = bytes.fromhex(self.identity.clients[client_id.decode()])
            Ed25519PublicKey.from_public_bytes(ltpk).verify(
                tlv[TlvValue.Signature], self._client_verify_pub + client_id + server_pub
            )
        except (KeyError, InvalidSignature, InvalidTag):
            _LOGGER.info("Unpaired device, asking it to pair")
            error = {TlvValue.SeqNo: b"\x04", TlvValue.Error: bytes([ErrorCode.Authentication])}
            self.send_to_client(FrameType.PV_Next, {"_pd": write_tlv(error)})
            return
        _LOGGER.info("Verified %s", client_id.decode())
        super()._m3_verify(pairing_data)

    # Remote commands

    def _handle_message(self, message):
        ident, content = message.get("_i"), message.get("_c", {})
        reply = {}

        if ident == "_systemInfo":
            port = self.transport.get_extra_info("sockname")[1]
            reply = self.identity.system_info(self.device_name, port)
        elif ident == "_hidC" and content.get("_hBtS") == 2:  # 2 = button released
            command = _enum(HidCommand, content.get("_hidC"))
            if command == HidCommand.Home and self.on_move:  # the TV button
                self.mouse_mode = not self.mouse_mode
                _LOGGER.info("Mouse mode %s", "on" if self.mouse_mode else "off")
            elif command == HidCommand.Select and self.mouse_mode:
                self._act("left_click")
            else:
                self._act(HID_ACTIONS.get(command))
        elif ident == "_mcc":
            command = _enum(MediaControlCommand, content.get("_mcc"))
            if command == MediaControlCommand.GetVolume:
                reply = {"_vol": self._volume}
            elif command == MediaControlCommand.SetVolume:
                # ponytail: absolute volume becomes one key step up/down; reading and setting
                # the real Windows volume needs the COM audio API (pycaw) if this feels off.
                new = content.get("_vol", self._volume)
                if new != self._volume:
                    self._act("volume_up" if new > self._volume else "volume_down")
                self._volume = new
            else:
                self._act(MCC_ACTIONS.get(command))
        elif ident == "_hidT":
            self._touch(content)
        elif ident == "_touchStart":
            self._touchpad = (content.get("_width", 1000.0), content.get("_height", 1000.0))
            reply = {"_i": 1}  # touch session id; the remote gives up without one
        elif ident == "FetchMediaControlStatus":
            reply = {"MediaControlFlags": int(MEDIA_FLAGS)}
        elif ident == "_sessionStart":
            reply = {"_sid": secrets.randbits(32)}
        elif ident == "TVRCSessionStart":
            reply = content
        elif ident == "FetchAttentionState":
            reply = {"state": 3}  # awake
        elif ident == "_interest" and "_iMC" in content.get("_regEvents", []):
            self._send("_iMC", message.get("_x", 0), 1, {"_mcF": int(MEDIA_FLAGS)})

        # Answer everything, even events and requests we don't know: tvremoted ends the
        # session on "No request handler" errors, and extra acks are ignored.
        self._reply(message, _c=reply)

    def _touch(self, content):
        """Mouse mode: drag moves the cursor. Otherwise swipe left/right: previous/next track. Swipe up/down: volume, longer = more."""
        phase, point = content.get("_tPh"), (content.get("_cx", 0), content.get("_cy", 0))
        if self.mouse_mode:
            # Only drag moves: the Release point jumps as the finger lifts.
            if phase in TOUCH_DRAG and self._touch_start:
                last, self._touch_start = self._touch_start, point
                # Carry sub-pixel remainders so slow drags don't stall or stutter.
                x = (point[0] - last[0]) * MOUSE_SPEED + self._mouse_rest[0]
                y = (point[1] - last[1]) * MOUSE_SPEED + self._mouse_rest[1]
                dx, dy = round(x), round(y)
                self._mouse_rest = (x - dx, y - dy)
                if dx or dy:
                    self.on_move(dx, dy)
            elif phase == TouchAction.Press.value:
                self._touch_start, self._mouse_rest = point, (0.0, 0.0)
            elif phase == TouchAction.Release.value:
                self._touch_start = None
            return
        if phase == TouchAction.Press.value:
            self._touch_start = point
        elif phase == TouchAction.Release.value and self._touch_start:
            dx, dy = point[0] - self._touch_start[0], point[1] - self._touch_start[1]
            self._touch_start = None
            width, height = self._touchpad
            if abs(dx) >= abs(dy) and abs(dx) > width * SWIPE_FRACTION:
                self._act("next" if dx > 0 else "previous")
            elif abs(dy) > abs(dx) and abs(dy) > height * SWIPE_FRACTION:
                steps = max(1, int(abs(dy) / (height * VOLUME_STEP_FRACTION)))
                for _ in range(steps):
                    self._act("volume_down" if dy > 0 else "volume_up")  # y grows downwards

    def _act(self, action):
        if action:
            _LOGGER.info("Action: %s", action)
            self.on_action(action)

    def _send(self, ident, xid, msg_type, content):
        self._write({"_i": ident, "_x": xid, "_t": msg_type, "_c": content})

    def _reply(self, request, **fields):
        # Responses carry no "_i"; the client matches them by "_x".
        self._write({"_x": request.get("_x", 0), "_t": RESPONSE, **fields})

    def _write(self, message):
        _LOGGER.debug("Sending: %s", message)
        self.send_to_client(FrameType.E_OPACK, message)


def _enum(enum_type, value):
    try:
        return enum_type(value)
    except ValueError:
        return None
