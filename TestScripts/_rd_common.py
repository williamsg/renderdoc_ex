"""
Common utilities for RenderDoc test scripts.

Handles renderdoc module loading and provides shared helper functions.
"""

import os
import sys
import json
import glob
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Default renderdoc install directory (Release build output)
DEFAULT_RD_DIR = os.path.join(PROJECT_ROOT, "x64", "Release")


def _detect_required_python(rd_dir):
    """Look for pythonXY.dll in rd_dir (and parent dirs) and return (major, minor) or None."""
    # Search in rd_dir itself, then parent (for cases like pymodules subdir)
    search_dirs = [rd_dir]
    parent = os.path.dirname(rd_dir)
    if parent != rd_dir:
        search_dirs.append(parent)

    for d in search_dirs:
        pattern = os.path.join(d, "python[0-9][0-9].dll")
        matches = glob.glob(pattern)
        if matches:
            basename = os.path.basename(matches[0])
            m = re.match(r"python(\d)(\d+)\.dll", basename)
            if m:
                return int(m.group(1)), int(m.group(2))
    return None


def setup_renderdoc(rd_dir=None):
    """Set up sys.path and environment so that `import renderdoc` works.

    Parameters
    ----------
    rd_dir : str or None
        Directory containing renderdoc.pyd.  If None, uses DEFAULT_RD_DIR.

    Returns
    -------
    bool
        True if renderdoc was successfully imported.
    """
    if rd_dir is None:
        rd_dir = DEFAULT_RD_DIR

    rd_dir = os.path.abspath(rd_dir)

    if not os.path.isdir(rd_dir):
        print("[ERROR] RenderDoc directory not found: %s" % rd_dir)
        return False

    # Check Python version compatibility
    required = _detect_required_python(rd_dir)
    if required is not None:
        current = (sys.version_info.major, sys.version_info.minor)
        if current != required:
            print("[ERROR] Python version mismatch!")
            print("  renderdoc.pyd requires Python %d.%d" % required)
            print("  Current Python: %d.%d" % current)
            print("  Please use the correct Python version.")
            return False

    # Build list of directories to try: rd_dir itself and its 'pymodules' subdir
    dirs_to_try = [rd_dir]
    pymodules_dir = os.path.join(rd_dir, "pymodules")
    if os.path.isdir(pymodules_dir):
        dirs_to_try.append(pymodules_dir)

    # We need the base rd_dir on PATH/dll_directory for renderdoc.dll dependency
    os.environ["PATH"] = rd_dir + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(rd_dir)
        except OSError:
            pass

    # Try each candidate directory for renderdoc.pyd
    for candidate in dirs_to_try:
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

        if candidate != rd_dir:
            os.environ["PATH"] = candidate + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(candidate)
                except OSError:
                    pass

        # Clear cached import failure so Python re-searches sys.path
        sys.modules.pop("renderdoc", None)

        try:
            import renderdoc  # noqa: F401
            print("[INFO] Successfully loaded renderdoc from: %s" % candidate)
            return True
        except ImportError:
            pass

    print("[ERROR] Failed to import renderdoc from %s" % rd_dir)
    if os.path.isdir(pymodules_dir):
        print("  Also tried: %s" % pymodules_dir)
    print("  Ensure renderdoc.pyd exists in one of these directories.")
    return False


def open_capture(rdc_path):
    """Open an RDC capture file and return (cap, controller).

    Caller is responsible for calling controller.Shutdown() and cap.Shutdown()
    when done.

    Parameters
    ----------
    rdc_path : str
        Path to the .rdc file.

    Returns
    -------
    (cap, controller) or (None, None) on failure.
    """
    import renderdoc as rd

    rd.InitialiseReplay(rd.GlobalEnvironment(), [])

    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(rdc_path, "", None)

    if result != rd.ResultCode.Succeeded:
        print("[ERROR] Failed to open capture: %s" % str(result))
        cap.Shutdown()
        rd.ShutdownReplay()
        return None, None

    if not cap.LocalReplaySupport():
        print("[ERROR] Capture cannot be replayed on this machine.")
        cap.Shutdown()
        rd.ShutdownReplay()
        return None, None

    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)

    if result != rd.ResultCode.Succeeded:
        print("[ERROR] Failed to open replay: %s" % str(result))
        cap.Shutdown()
        rd.ShutdownReplay()
        return None, None

    print("[INFO] Capture opened successfully: %s" % rdc_path)
    return cap, controller


def close_capture(cap, controller):
    """Cleanly shut down controller and capture file."""
    import renderdoc as rd

    if controller is not None:
        controller.Shutdown()
    if cap is not None:
        cap.Shutdown()
    rd.ShutdownReplay()
    print("[INFO] Replay shut down.")


def flatten_actions(root_actions):
    """Recursively flatten the action tree into a list of leaf drawcall actions."""
    result = []
    for action in root_actions:
        if action.children:
            result.extend(flatten_actions(action.children))
        else:
            result.append(action)
    return result


def get_drawcalls(root_actions):
    """Get only actual drawcall actions (filtered by ActionFlags.Drawcall)."""
    import renderdoc as rd
    all_actions = flatten_actions(root_actions)
    return [a for a in all_actions if a.flags & rd.ActionFlags.Drawcall]
