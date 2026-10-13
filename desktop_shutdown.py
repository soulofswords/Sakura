"""Bounded shutdown after the user actually closes the native window."""
import os
import threading

def arm_shutdown(cleanup, timeout=8, exit_process=os._exit):
    # Native libraries/executor threads can outlive Qt even after cleanup.
    # Exit successfully only after an intentional window close, never on errors.
    def finish():
        done = threading.Event()
        def release():
            try:
                cleanup()
            finally:
                done.set()
        threading.Thread(target=release, daemon=True).start()
        done.wait(timeout)
        exit_process(0)
    threading.Thread(target=finish, daemon=True).start()
