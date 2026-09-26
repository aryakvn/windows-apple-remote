"""Turn remote actions into OS key presses. Windows only for now."""

import ctypes
import ctypes.wintypes
import sys

# Windows virtual-key codes
VIRTUAL_KEYS = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "back": 0x1B,  # Escape
}
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x2, 0x4
KEYEVENTF_EXTENDEDKEY = 0x1
KEYEVENTF_KEYUP = 0x2
NOT_EXTENDED = {0x1B}

SUPPORTED = sys.platform == "win32"


def press(action):
    """Tap the key mapped to `action`."""
    if action == "left_click":
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        return
    vk = VIRTUAL_KEYS[action]
    flags = 0 if vk in NOT_EXTENDED else KEYEVENTF_EXTENDEDKEY
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, flags, 0)
    user32.keybd_event(vk, 0, flags | KEYEVENTF_KEYUP, 0)


def move(dx, dy):
    """Move the cursor by exactly (dx, dy) pixels.

    SetCursorPos instead of a relative mouse_event: Windows pointer acceleration
    scales each small relative step differently, which made touch drags jumpy.
    """
    user32 = ctypes.windll.user32
    point = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    user32.SetCursorPos(point.x + dx, point.y + dy)
