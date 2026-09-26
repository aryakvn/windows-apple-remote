# Changelog

<!--
Maintained for both humans and Claude Code to reference. Before
implementing a feature or fix, check the entries below first — it may
already be done, which saves searching the whole codebase.

Format (based on Keep a Changelog: https://keepachangelog.com/en/1.1.0/):
- New entries go under "## [Unreleased]" until a release is cut.
- Categories: Added, Changed, Fixed, Deprecated, Removed, Security.
  Only add a category heading once it has an entry under it.
- One bullet per entry, imperative mood, one line where possible:
    - Add CSV export to the reports page. (Refs: JIRA-482, #210)
- Include "(Refs: ...)" only when there's an external reference — a Jira
  key, GitHub issue/PR number, Trello card title/URL, or similar tracker
  ID. Comma-separate multiple references. Omit the parenthetical entirely
  if there's nothing to reference.
- To cut a release: rename "## [Unreleased]" to "## [X.Y.Z] - YYYY-MM-DD"
  and start a fresh, empty "## [Unreleased]" section above it.
- Never delete or rewrite past entries — only append.
-->

## [Unreleased]

## [0.2.0] - 2026-09-26

### Added

- Add mouse mode: the remote's TV button toggles it, then dragging on the touch area moves the cursor and a tap left-clicks.
- Document mouse mode, `pipx`/`py -m pip`/`python -m atv_remote` installs, and the `--address` fix for a PC that doesn't show up on the iPhone in the README.

## [0.1.2] - 2026-09-26

### Fixed

- Fall back to the default-route IP when Windows refuses the mDNS multicast route lookup (`WinError 10065`), so `atv-remote` starts on PCs with VPN or VM adapters.

## [0.1.1] - 2026-09-24

### Changed
- Rename the PyPI package from `atv-remote-server` to `windows-apple-remote` to match the repository and the PyPI trusted publisher; the `atv-remote` command and `atv_remote` import are unchanged.

### Fixed
- Fix the PyPI upload failing with `400 Non-user identities cannot create new projects` (package name didn't match the pending publisher); 0.1.0 was never uploaded.

## [0.1.0] - 2026-09-24

### Added
- Add `atv-remote` server that advertises the PC as an Apple TV (Companion protocol via pyatv) so the iOS Apple TV Remote can pair with a PIN and control media keys, volume, arrows, Enter and Escape on Windows.
- Add per-install identity, random pairing PIN per attempt, and rejection of unpaired devices on pair-verify.
- Add end-to-end tests that pair and send commands using pyatv's own client.
- Add GitHub Actions for Windows CI and PyPI trusted publishing on release.
- Add TestPyPI dry-run publishing (manual workflow run), a release-tag/version check and `twine check` to the publish workflow; run CI on every push.
- Add GitHub project links (aryakvn/windows-apple-remote) to the README and package metadata, with PyPI trusted-publisher setup steps.

### Fixed
- Encrypt the connection right after pair-setup, since iOS keeps using it, and parse only OPACK frame types, which fixes the `TypeError: 0xc9` disconnect after pairing.
- Answer `_systemInfo` with device info, reply "No request handler" to unknown requests and drop `_i` from responses to match a real Apple TV; log outgoing messages with `-v`.
- Decode OPACK back-references the way Apple encodes them (skip 1-byte objects like `''`); pyatv's decoder was off by one, so iOS 27's `_systemInfo` arrived without its `_i` and was rejected.
- Keep the iOS remote session open: answer every message successfully (replacing the "No request handler" errors), return a touch session id from `_touchStart` and flags from `FetchMediaControlStatus`, and send a full Apple TV `_systemInfo` (`_lP`, `_stA` with `com.apple.tvremoteservices`, Siri peer data) with `rpFl=0xB6782` and model `AppleTV5,3`, matching thiccaxe/CompanionGames, a server known to work with the remote.

### Changed
- Make the touch area a media controller: tap plays/pauses, swipe left/right changes track, swipe up/down changes volume (longer swipe = more steps); D-pad directions map the same way.
- Advertise volume control (`_mcF` Volume flag) so the iPhone's volume buttons control the PC, and turn `SetVolume` into volume key steps.

### Removed
- Remove arrow-key, Enter and ±10s skip mappings, which the touch-only iOS remote can't reach.