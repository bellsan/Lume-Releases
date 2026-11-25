"""Drive the real packaged WebView2 UI on the Windows CI runner.

Only the test harness changes: never modify the application or its archive.
A missing button, rejected invocation or lingering native process fails CI.
"""
import sys
import time
import threading
from pathlib import Path
from queue import Queue


def drive_native_quit(info, proc):
    import comtypes
    from pywinauto import Desktop

    hwnd = int(info["hwnd"])
    pid = int(info["pid"])
    desktop = Desktop(backend="uia")
    root = desktop.window(handle=hwnd)

    def button(name, timeout=35):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                for item in root.descendants(control_type="Button"):
                    if item.element_info.name.strip() == name and item.is_enabled():
                        return item
            except Exception:
                pass
            if proc.poll() is not None:
                raise RuntimeError("App exited before " + name)
            time.sleep(.4)
        try:
            print("Accessible buttons:", [x.element_info.name for x in root.descendants(control_type="Button")], flush=True)
        except Exception as exc:
            print("UIA tree unavailable:", repr(exc), flush=True)
        raise RuntimeError("Native UI button not found: " + name)

    def invoke_async(item):
        # A JavaScript confirmation can block InvokePattern until answered.
        errors = Queue()
        runtime_id = item.element_info.runtime_id
        name = item.element_info.name
        def run():
            comtypes.CoInitialize()
            try:
                # Resolve the element again in this COM apartment.
                from pywinauto import Desktop
                d = Desktop(backend="uia")
                r = d.window(handle=hwnd)
                for candidate in r.descendants(control_type="Button"):
                    if candidate.element_info.runtime_id == runtime_id:
                        candidate.invoke()
                        return
                raise RuntimeError("UI element disappeared: " + name)
            except Exception as exc:
                errors.put(exc)
            finally:
                comtypes.CoUninitialize()
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread, errors

    settings = button("設定")
    settings.invoke()
    quit_button = button("終了する")
    # Ensure the intended application action is invoked, not an API shortcut.
    thread, errors = invoke_async(quit_button)
    end = time.monotonic() + 35
    confirmed = False
    while time.monotonic() < end:
        if not errors.empty():
            raise RuntimeError("Quit button invocation failed") from errors.get()
        if proc.poll() is not None:
            # The original smoke test still checks clean exit, marker removal and native process exit.
            print("Native settings quit invoked; supervisor exited", flush=True)
            return
        if not confirmed:
            try:
                # Only inspect our own app's windows, not unrelated runner windows.
                candidates = [root] + desktop.windows(process=pid, visible_only=True)
                for win in candidates:
                    for item in win.descendants(control_type="Button"):
                        if item.element_info.name.strip().casefold() in {"ok", "yes", "はい", "確認"} and item.is_enabled() and item.is_visible():
                            print("Accepting native confirmation:", item.element_info.name, flush=True)
                            item.invoke()
                            confirmed = True
                            break
                    if confirmed:
                        break
            except Exception as exc:
                print("Confirmation lookup:", repr(exc), flush=True)
        time.sleep(.4)
    raise RuntimeError("Native settings quit did not complete; confirmation accepted=" + str(confirmed))


def main():
    path = Path(sys.argv[1]).resolve()
    sys.argv = [str(path), *sys.argv[2:]]
    source = path.read_text(encoding="utf-8")
    start = "        # Drive the real WebView2 DOM, not the shutdown API."
    end = "        assert proc.wait(timeout=60)==0"
    if source.count(start) != 1:
        raise RuntimeError("Unexpected native test layout")
    first = source.index(start)
    last = source.index(end, first)
    source = source[:first] + "        drive_native_quit(info, proc)\n" + source[last:]
    # No remote debugging flag is necessary for UI Automation.
    old = "env=dict(os.environ,LOCALAPPDATA=temp,WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=f'--remote-debugging-address=127.0.0.1 --remote-debugging-port={debug_port}')"
    if source.count(old) != 1:
        raise RuntimeError("Unexpected debug configuration")
    source = source.replace(old, "env=dict(os.environ,LOCALAPPDATA=temp)")
    exec(compile(source, str(path), "exec"), {"__name__": "__main__", "__file__": str(path), "drive_native_quit": drive_native_quit})


if __name__ == "__main__":
    main()
