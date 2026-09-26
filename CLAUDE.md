# CLAUDE.md — windows-apple-remote

Makes a Windows PC appear as an Apple TV so the iOS **Apple TV Remote** (Control
Center) can pair with it and send media keys. PyPI name `windows-apple-remote`, import
`atv_remote`, CLI `atv-remote`. macOS support is planned; HomeKit is out of scope.

## Status (2026-09-24)

- Session now stays open on the iPhone (CompanionGames-style replies fixed it).
  The iOS 27 remote shows only a touch area, so control is gesture-based.

- Working against a real iPhone (iOS 27.0, iPhone12,1): mDNS discovery, pair-setup
  with PIN, pair-verify on reconnect, encrypted session, `_systemInfo` decode.
- Earlier the iPhone sent `TVRCSessionStop` ~30 ms after setup; fixed by the replies
  listed below. Gestures and hardware-volume routing (`_mcF` Volume bit 0x100) are
  not yet confirmed on a device.

## Layout

- `src/atv_remote/server.py` — `RemoteServer` (one asyncio.Protocol per connection,
  subclasses pyatv's `CompanionServerAuth`), `Identity`, `unpack_opack`.
- `src/atv_remote/keys.py` — action name → Windows virtual key via `keybd_event`.
  Swap/extend this for macOS. `SUPPORTED` gates the CLI.
- `src/atv_remote/cli.py` — argparse, TCP server, zeroconf `_companion-link._tcp`
  registration, PIN printing.
- `tests/test_server.py` — pyatv's own Companion client pairs and presses buttons
  end to end; wrong PIN / unpaired device rejected; OPACK regression; replay of the
  iOS 27 request sequence.
- `.github/workflows/ci.yml` (Windows, py3.10–3.13), `publish.yml` (GitHub release →
  PyPI trusted publishing, environment `pypi`). Version lives in
  `src/atv_remote/__init__.py` (hatch dynamic version).

## Reusable pieces

- `Identity(path)` — persistent server identity in JSON: `id` (UUID), `seed` (32 bytes,
  Ed25519/X25519 key seed), `clients` (pairing id → client Ed25519 public key hex).
  `txt_record()` gives the mDNS TXT; `system_info(name, port)` gives the `_systemInfo`
  reply. All ids derived deterministically from the seed. Default path
  `%APPDATA%\atv-remote\state.json`; delete it to forget all paired devices.
- `unpack_opack(data)` — correct OPACK decoder (wraps pyatv's `_unpack` with a fixed
  back-reference table). Use this instead of `pyatv.support.opack.unpack` for anything
  coming from iOS.
- `keys.press(action)` — actions: `play_pause next previous volume_up volume_down up
  down left right select back`.

## Protocol facts learned (Companion / "rapport")

Discovery and auth:
- Modern iOS Remote uses the **Companion** protocol (`_companion-link._tcp`), not MRP.
- TXT values known to work: `rpFl=0xB6782`, `rpMd=AppleTV5,3`, `rpMac=2`, plus
  `rpHN rpHA rpAD rpHI` (12 hex chars each), `rpBA` (MAC), `rpMRtID` (server id).
- Frame: 1 byte type + 3 byte big-endian length + payload. Encrypted payloads use
  ChaCha20-Poly1305, 12-byte nonce counter, AAD = the 4-byte header, +16 byte tag.
- **After pair-setup M6, iOS keeps the same connection and encrypts immediately**
  with `hkdf("", "ServerEncrypt-main"/"ClientEncrypt-main", SRP session key)`. pyatv's
  client disconnects after pairing, so its tests never exercise this.
- pyatv's `CompanionServerAuth` weaknesses we override: fixed PIN 1111 (its `pin`
  arg is ignored), public fixed private key, and `_m3_verify` never checks the
  client's signature (any device could connect unpaired). We use a random PIN per
  pairing attempt, a per-install seed, verify the controller signature in M5, and
  verify the M3 signature against the stored client key.

OPACK:
- **pyatv 0.18 `opack.unpack` bug:** it adds 1-byte objects (`''`, `b''`) to the
  back-reference table and dedupes by `==`. Apple's encoder (and pyatv's own `pack`)
  skips 1-byte objects, so any message containing `''` resolves later references one
  slot off. iOS 27's `_systemInfo` has `'myriadTrialTreatment': ''`, which turned the
  top-level `_i` into another value. Fixed by `_RefTable` in server.py. Worth
  reporting upstream to pyatv.

Messages (`_t`: 1=event, 2=request, 3=response; responses match on `_x`, carry no `_i`):
- iOS 27 sequence after pair-verify: `_systemInfo`, `_sessionStart`
  (`_srvT=com.apple.tvremoteservices`), `TVRCSessionStart` (`ProtocolVersionKey
  1.2`), `FetchAttentionState`, `FetchSiriRemoteInfo`, `_interest`
  (PushSiriRemoteInfo, SupportedActions, NowPlayingInfo, TopShelfItems,
  MediaControlStatus), `FetchSupportedActionsEvent`,
  `FetchCurrentNowPlayingInfoEvent`, `FetchCurrentTopShelfItemsEvent`,
  `FetchMediaControlStatus`, `_touchStart`, `_tiStart`.
- Replies that did **not** keep the session open: empty `{}` for everything, and
  `No request handler` errors (code 58822, RPErrorDomain) for unknown requests.
- Replies now sent (from CompanionGames): a normal `{}` reply to every message, never
  an error; `_touchStart` → `{"_i": 1}`; `FetchMediaControlStatus` →
  `{"MediaControlFlags": flags}`; `FetchAttentionState` → `{"state": 3}`;
  `_sessionStart` → `{"_sid": random32}`; `TVRCSessionStart` echoes its content;
  `_systemInfo` → name, model, `_i`, `_idsID`, `_pubID`, `_mrID`, `_mRtID`,
  `_lP` (listening port), `_stA` (must include `com.apple.tvremoteservices`),
  `_sf 65536`, `_bf 1920`, `_cf 512`, `_clFl 128`, `_msSt/_msRo/_dCapF 1`, and
  `_siriInfo.peerData` with `userInterfaceIdiom: "ZEUS"` (Apple TV).
- Input: `_hidC` with `_hBtS` 1=down / 2=up and `_hidC` = pyatv `HidCommand`; a tap
  on the touchpad also arrives as `_hidC` Select. `_hidT` touch events: `_tPh`
  1=start, 2=move (iOS 27; pyatv's `TouchAction` has 3=Hold), 4=end, 5=click; `_cx/_cy` 0–1000. `_mcc` = pyatv
  `MediaControlCommand` (`SkipBy` carries `_skpS`).
- Real `FetchSiriRemoteInfo` reply is `{"SiriRemoteInfoKey": <NSKeyedArchiver
  bplist of TVRCSiriRemoteInfo>}`; `SupportedActions` event carries
  `GuideSupportedKey`; `NowPlayingInfo` event carries `NowPlayingInfoKey` bplist
  (`TVRCNowPlayingInfo`, `playbackRate`). Not implemented; see pyatv issues #2325
  and #2461.

## README format

Keep `README.md` in this shape so every release reads the same:

1. `# windows-apple-remote` (repo name), then the CI and PyPI badges, then
   `Package: [\`windows-apple-remote\`](pypi link) · Source: [github.com/aryakvn/windows-apple-remote](repo link)`.
2. One short paragraph: what it does (iOS Apple TV Remote → Windows media keys, via pyatv).
3. Mapping table with columns `Remote (touch area) | PC`, one row per gesture or
   button. It must match `HID_ACTIONS`, `MCC_ACTIONS` and `_touch()` in `server.py`;
   update it in the same commit as any mapping change.
4. `## Install & run`: `pip install windows-apple-remote` + `atv-remote`, then the
   `pip install git+https://github.com/aryakvn/windows-apple-remote.git` alternative,
   the pairing steps (same Wi-Fi, Control Center → Apple TV Remote, PIN in terminal),
   and an `Options:` block listing every `cli.py` flag with a one-line comment.
5. `## Notes`: firewall, state file location, behaviour limits, platform support.
6. `## Development`: clone, venv, `pip install -e ".[test]"`, `pytest`, and the
   editable-install warning.
7. `## Releasing to PyPI`: one-time trusted-publisher values and the per-release
   steps (keep them in sync with the release process below).

Style: short sentences, second person, Windows commands (`.venv\Scripts\activate`).
Files must stay UTF-8. On Windows, Python's `read_text()`/`write_text()` default to
cp1252 and `"\a"` in a normal string becomes a bell character; use the Edit tool or
bytes with explicit `utf-8`.

## Release process

Versioning is semver: patch for fixes, minor for features; while 0.x, a breaking
change bumps the minor. Tags are `vX.Y.Z`. Work reaches `main` only through a PR
from a feature branch; the release commit is the only thing pushed straight to `main`.

1. `main` is up to date and its CI is green.
2. Bump `__version__` in `src/atv_remote/__init__.py` (if not bumped yet).
3. Cut the changelog (`changelog:release` skill): rename `## [Unreleased]` to
   `## [X.Y.Z] - YYYY-MM-DD` and add an empty `## [Unreleased]` above it. Don't touch
   any entry.
4. Commit on `main` with the message `Release X.Y.Z` (plus the co-author trailer).
5. Annotated tag: `git tag -a vX.Y.Z -m "windows-apple-remote X.Y.Z"`, then push `main`
   and the tag.
6. GitHub release: tag `vX.Y.Z`, title `vX.Y.Z`, body:

   ````markdown
   <one-line summary of the release>

   ```
   pip install windows-apple-remote
   atv-remote
   ```

   <the X.Y.Z section of CHANGELOG.md, copied as is: ### Added / Changed / Fixed / Removed>
   ````

   If something in the release hasn't been tried on a real iPhone, add a
   `### Known issues` section at the end saying what.
7. This machine has no `gh` or GitHub login (git pushes over SSH), so build the URL
   `https://github.com/aryakvn/windows-apple-remote/releases/new?tag=vX.Y.Z&title=vX.Y.Z&body=<url-encoded body>`
   and open it with PowerShell `Start-Process`; the user clicks **Publish release**.
   PRs work the same way via `.../compare/main...<branch>?expand=1&title=...&body=...`.
8. Publishing the release runs `publish.yml`: tests, tag vs `__version__` check,
   build, `twine check`, upload to PyPI. PyPI versions can't be reused, so offer a
   TestPyPI dry run first (run the Publish workflow by hand) when a change is untested.
9. Check the Actions run; if the upload failed because the trusted publisher wasn't
   set up yet, re-run the failed job after the user adds it.

## References

- pyatv protocol docs: docs/documentation/protocols.md in postlund/pyatv.
- pyatv issue #2325 "[Companion] Documentation Dumps" — real Apple TV message dumps.
- thiccaxe/CompanionGames — a working Companion server for the iOS remote.
  **AGPL**: take protocol facts only, never copy code (this package is MIT).
- pyatv's `scripts/atvproxy.py companion` can MITM a real Apple TV to capture replies.

## Gotchas

- Dev install must be editable: `pip install -e ".[test]"`. A plain `pip install .`
  puts a stale copy in `site-packages` and source edits stop taking effect (this
  happened repeatedly while debugging; check traceback paths).
- pyatv is pinned `>=0.18,<0.19` because we use internals (`CompanionServerAuth`,
  `opack._unpack`, companion framing). Re-check the OPACK fix and auth overrides
  before bumping.
- Windows Firewall must allow Python on private networks (TCP port + UDP 5353).
- Windows has one Play/Pause key, so Play and Pause both toggle.
- Without the Volume bit (0x100) in `_mcF`, iOS doesn't route the iPhone's volume
  buttons to the device. `SetVolume` (absolute `_vol`) is turned into one relative
  key step.
- `atv-remote.exe` running locks the venv: pip can't reinstall (WinError 32) and may
  leave the package uninstalled. Stop the server before `pip install -e .`, or run
  tests with `PYTHONPATH=src`.
- Run with `atv-remote -v` to log every received and sent message.
- The PyPI trusted publisher's project name must equal `name` in `pyproject.toml`
  (`windows-apple-remote`). A mismatch still passes the token exchange but the upload
  fails with `400 Non-user identities cannot create new projects`. That is why v0.1.0
  (published as `atv-remote-server`) never reached PyPI and 0.1.1 is the first upload.
- Distribution name is `windows-apple-remote`, but the import package stays
  `atv_remote` and the command stays `atv-remote`.
