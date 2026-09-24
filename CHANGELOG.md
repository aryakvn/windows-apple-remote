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

### Added
- Add `atv-remote` server that advertises the PC as an Apple TV (Companion protocol via pyatv) so the iOS Apple TV Remote can pair with a PIN and control media keys, volume, arrows, Enter and Escape on Windows.
- Add per-install identity, random pairing PIN per attempt, and rejection of unpaired devices on pair-verify.
- Add end-to-end tests that pair and send commands using pyatv's own client.
- Add GitHub Actions for Windows CI and PyPI trusted publishing on release.

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
