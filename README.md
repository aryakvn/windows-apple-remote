# atv-remote-server

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

## Install & run

```sh
pip install atv-remote-server
atv-remote
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
pip install -e ".[test]"
pytest
```

The tests use pyatv's own client to pair with the server and press buttons end to end.

Releases: bump `__version__` in `src/atv_remote/__init__.py`, then publish a GitHub
release. The `publish` workflow builds and uploads to PyPI using
[trusted publishing](https://docs.pypi.org/trusted-publishers/) — add this repo as a
trusted publisher on PyPI (workflow `publish.yml`, environment `pypi`) once.
