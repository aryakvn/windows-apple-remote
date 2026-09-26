# windows-apple-remote

[![CI](https://github.com/aryakvn/windows-apple-remote/actions/workflows/ci.yml/badge.svg)](https://github.com/aryakvn/windows-apple-remote/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/windows-apple-remote)](https://pypi.org/project/windows-apple-remote/)

Package: [`windows-apple-remote`](https://pypi.org/project/windows-apple-remote/) · Source:
[github.com/aryakvn/windows-apple-remote](https://github.com/aryakvn/windows-apple-remote)

Control your Windows PC's media with the **Apple TV Remote** on your iPhone or iPad
(Control Center → Apple TV Remote). The PC advertises itself as an Apple TV over the
Companion protocol using [pyatv](https://pyatv.dev), and turns remote buttons into
media keys.

| Remote (touch area)                  | PC                                   |
|---------------------------------------|--------------------------------------|
| Tap                                   | Play/Pause                           |
| Swipe right / left                    | Next / Previous track                |
| Swipe up / down (longer = more)       | Volume Up / Down                     |
| iPhone volume buttons                 | Volume Up / Down                     |
| Back (Menu)                           | Escape                               |
| TV button                             | Toggle mouse mode                    |
| Drag / Tap (mouse mode)               | Move cursor / Left click             |

## Install & run

```sh
pip install windows-apple-remote
atv-remote
```

Or the latest code from GitHub:

```sh
pip install git+https://github.com/aryakvn/windows-apple-remote.git
```

Then on the iPhone (same Wi-Fi network): Control Center → Apple TV Remote → pick your
PC's name. The first time, a 4-digit PIN is printed in the terminal; type it on the
phone. The phone is remembered afterwards.

Options:

```
atv-remote --name "Living Room PC"   # name shown on the phone (default: hostname)
atv-remote --address 192.168.1.20    # IP to advertise if auto-detect picks the wrong adapter
atv-remote --port 49200              # fixed TCP port (useful for firewall rules)
atv-remote -v                        # debug logging
```

## Notes

- **Windows Firewall:** allow Python on private networks when prompted, or the phone
  can't connect. mDNS (UDP 5353) must be allowed too.
- **Forget all paired devices:** delete `%APPDATA%\atv-remote\state.json`. It also
  holds this PC's private identity key, so keep it private.
- Media and volume keys are global; Back (Escape) goes to the focused window.
- Windows has a single Play/Pause key, so the remote's separate Play and Pause both toggle.
- Now-playing info and the volume slider are not supported (they need AirPlay/MRP).
- macOS support is planned. HomeKit is not supported.

## Development

```sh
git clone https://github.com/aryakvn/windows-apple-remote.git
cd windows-apple-remote
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
pytest
```

Use `pip install -e` (editable). A plain `pip install .` copies the code into the venv
and later edits stop taking effect. Stop a running `atv-remote` before reinstalling;
Windows locks its executable.

The tests use pyatv's own client to pair with the server and press buttons end to end.
Bugs and ideas: [issues](https://github.com/aryakvn/windows-apple-remote/issues).

## Releasing to PyPI

Publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), so no
API token is stored in GitHub. One-time setup:

1. On [pypi.org](https://pypi.org/manage/account/publishing/) add a *pending publisher*:
   project `windows-apple-remote`, owner `aryakvn`, repository `windows-apple-remote`,
   workflow `publish.yml`, environment `pypi`.
2. Optional dry run: do the same on [test.pypi.org](https://test.pypi.org/manage/account/publishing/)
   with environment `testpypi`.

Each release:

1. Bump `__version__` in `src/atv_remote/__init__.py` and move the `Unreleased`
   entries in `CHANGELOG.md` under the new version.
2. Optional: run the **Publish** workflow by hand (Actions tab) to upload to TestPyPI.
3. Publish a GitHub release tagged `vX.Y.Z` (matching `__version__`). The workflow runs
   the tests, checks the tag against the version, builds, and uploads to PyPI.
