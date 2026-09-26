# windows-apple-remote

[![CI](https://github.com/aryakvn/windows-apple-remote/actions/workflows/ci.yml/badge.svg)](https://github.com/aryakvn/windows-apple-remote/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/windows-apple-remote)](https://pypi.org/project/windows-apple-remote/)

Package: [`windows-apple-remote`](https://pypi.org/project/windows-apple-remote/) · Source:
[github.com/aryakvn/windows-apple-remote](https://github.com/aryakvn/windows-apple-remote)

Control your Windows PC's media and mouse with the **Apple TV Remote** on your iPhone
or iPad (Control Center → Apple TV Remote). The PC advertises itself as an Apple TV over
the Companion protocol using [pyatv](https://pyatv.dev), and turns remote gestures into
media keys. Press the TV button to switch the touch area into a trackpad.

| Remote (touch area)                  | PC                                   |
|---------------------------------------|--------------------------------------|
| Tap                                   | Play/Pause                           |
| Swipe right / left                    | Next / Previous track                |
| Swipe up / down (longer = more)       | Volume Up / Down                     |
| iPhone volume buttons                 | Volume Up / Down                     |
| Back (Menu)                           | Escape                               |
| TV button                             | Switch between remote and mouse mode |
| Drag (mouse mode)                     | Move the cursor                      |
| Tap (mouse mode)                      | Left click                           |

## Install & run

Install from [PyPI](https://pypi.org/project/windows-apple-remote/) and start it:

```sh
pip install windows-apple-remote
atv-remote
```

Other ways to install:

```sh
pipx install windows-apple-remote     # isolated install, atv-remote on your PATH
py -m pip install windows-apple-remote  # if pip isn't on your PATH
pip install git+https://github.com/aryakvn/windows-apple-remote.git  # latest code from GitHub
```

If `atv-remote` isn't recognized (pip's `Scripts` folder isn't on your PATH), run it
through Python instead. It takes the same options:

```sh
python -m atv_remote
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

### Mouse mode

Press the TV button (bottom right of the remote) to switch to mouse mode; the terminal
prints `Mouse mode on`. Drag on the touch area to move the cursor and tap to left-click.
Press the TV button again to go back to media controls.

### If the PC doesn't show up on the iPhone

Your PC probably has more than one network adapter (VPN, Hyper-V, WSL, VirtualBox) and
`atv-remote` advertised the wrong one. Check the address in the `is live on` line. If it
isn't your Wi-Fi/Ethernet IP, find the right one with `ipconfig` (the adapter on the same
network as the phone) and pass it:

```sh
atv-remote --address 192.168.0.98
python -m atv_remote --address 192.168.0.98   # same, if atv-remote isn't recognized
```

Also check that the phone is on the same network and that the firewall allows Python
(see Notes).

## Notes

- **Windows Firewall:** allow Python on private networks when prompted, or the phone
  can't connect. mDNS (UDP 5353) must be allowed too.
- **Forget all paired devices:** delete `%APPDATA%\atv-remote\state.json`. It also
  holds this PC's private identity key, so keep it private.
- Media and volume keys are global; Back (Escape) and mouse clicks go to the window under
  the cursor or in focus.
- Mouse mode moves the cursor exactly as far as you drag (no Windows pointer
  acceleration). To change the speed, edit `MOUSE_SPEED` in `server.py`.
- `-v` prints every touch event and can make the cursor lag; leave it off for normal use.
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
