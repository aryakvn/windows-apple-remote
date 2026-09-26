"""Command line entry point: advertise this PC as an Apple TV and serve remotes."""

import argparse
import asyncio
import logging
import os
import socket
import sys
from pathlib import Path

from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from atv_remote import keys
from atv_remote.server import Identity, RemoteServer

SERVICE_TYPE = "_companion-link._tcp.local."


def default_state_path():
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    return Path(base) / "atv-remote" / "state.json"


def local_ip():
    """IP of the interface that routes to mDNS multicast, else to the internet (no packet is sent).

    With VPN/VM adapters Windows can refuse the multicast lookup (WinError 10065).
    """
    for host in ("224.0.0.251", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((host, 5353))
                return sock.getsockname()[0]
        except OSError:
            pass
    return socket.gethostbyname(socket.gethostname())


def show_pin(pin):
    print(f"\n  Pairing PIN: {pin}\n  Enter it on your iPhone/iPad.\n", flush=True)


async def serve(args):
    identity = Identity(args.state)
    loop = asyncio.get_running_loop()
    server = await loop.create_server(
        lambda: RemoteServer(identity, args.name, keys.press, show_pin), "0.0.0.0", args.port
    )
    port = server.sockets[0].getsockname()[1]
    ip = args.address or local_ip()

    zeroconf = AsyncZeroconf(interfaces=[ip])
    info = ServiceInfo(
        SERVICE_TYPE,
        f"{args.name}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties=identity.txt_record(),
    )
    await zeroconf.async_register_service(info)
    print(f"'{args.name}' is live on {ip}:{port}.")
    print("Open Apple TV Remote (Control Center) on your iPhone and pick it. Ctrl+C to quit.")
    try:
        await asyncio.Event().wait()
    finally:
        await zeroconf.async_unregister_service(info)
        await zeroconf.async_close()
        server.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="atv-remote", description="Control this PC's media with the iOS Apple TV Remote."
    )
    parser.add_argument("--name", default=socket.gethostname(), help="name shown on the iPhone")
    parser.add_argument("--address", help="IP to advertise (default: auto-detect)")
    parser.add_argument("--port", type=int, default=0, help="TCP port (default: random)")
    parser.add_argument("--state", type=Path, default=default_state_path(), help="identity/pairings file")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    if not keys.SUPPORTED:
        parser.exit(1, "atv-remote supports Windows only for now.\n")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if not args.verbose:
        logging.getLogger("pyatv").setLevel(logging.WARNING)
    try:
        asyncio.run(serve(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
