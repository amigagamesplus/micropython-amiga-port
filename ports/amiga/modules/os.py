# os module for AmigaOS — wraps the C uos module and adds Python extensions.
from uos import *
import _ospath as path


def makedirs(name, exist_ok=False):
    """Recursive directory creation."""
    import uos
    # Handle AmigaOS paths: "Volume:path/to/dir"
    volume = ""
    rest = name
    if ":" in name:
        idx = name.index(":")
        volume = name[: idx + 1]
        rest = name[idx + 1 :]

    parts = rest.split("/") if rest else []

    current = volume if volume else ""
    for part in parts:
        if not part:
            continue
        if current and not current.endswith(":"):
            current = current + "/" + part
        else:
            current = current + part
        try:
            uos.mkdir(current)
        except OSError as e:
            if exist_ok and e.errno == 17:  # EEXIST
                pass
            else:
                raise


def walk(top, topdown=True):
    """Directory tree generator."""
    import uos
    try:
        entries = uos.listdir(top)
    except OSError:
        return

    dirs = []
    files = []
    for entry in entries:
        if not top.endswith(":") and not top.endswith("/"):
            full = top + "/" + entry
        else:
            full = top + entry
        try:
            s = uos.stat(full)
            if s[0] & 0o170000 == 0o040000:  # S_IFDIR
                dirs.append(entry)
            else:
                files.append(entry)
        except OSError:
            files.append(entry)

    if topdown:
        yield (top, dirs, files)

    for d in dirs:
        if not top.endswith(":") and not top.endswith("/"):
            new_path = top + "/" + d
        else:
            new_path = top + d
        yield from walk(new_path, topdown)

    if not topdown:
        yield (top, dirs, files)
