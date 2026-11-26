"""Make bundled PortAudio discoverable without ldconfig or binutils."""

import ctypes
import ctypes.util
from pathlib import Path
from sys import prefix

_find_library = ctypes.util.find_library
_portaudio = Path(prefix).parent / "lib" / "libportaudio.so.2"


def _find_bundled_portaudio(name):
    if name == "portaudio":
        try:
            ctypes.CDLL(str(_portaudio))
        except OSError:
            pass
        else:
            return str(_portaudio)
    return _find_library(name)


ctypes.util.find_library = _find_bundled_portaudio
