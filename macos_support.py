"""Lazy Apple APIs: importing this module is safe on Windows too."""
import os


def cursor_position():
    import Quartz
    bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    point = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return {'x': (point.x - bounds.origin.x) / max(1, bounds.size.width) * 2 - 1,
            'y': (point.y - bounds.origin.y) / max(1, bounds.size.height) * 2 - 1}


def mask_companion(image, window):
    """Pillow's Retina capture is 2x; normalize to logical main-display pixels."""
    import Quartz
    from PIL import ImageDraw
    bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    image = image.resize((int(bounds.size.width), int(bounds.size.height)))
    if window:
        left = max(0, int(window['x'] - bounds.origin.x))
        top = max(0, int(window['y'] - bounds.origin.y))
        right = min(image.width, int(window['x'] - bounds.origin.x + window['width']))
        bottom = min(image.height, int(window['y'] - bounds.origin.y + window['height']))
        if right > left and bottom > top:
            ImageDraw.Draw(image).rectangle((left, top, right, bottom), fill=(24, 24, 24))
    return image


def start_hotkey(callback, shortcut='<ctrl>+<shift>+t'):
    """Never enable click-through without a global recovery shortcut."""
    try:
        import Quartz
        if not Quartz.AXIsProcessTrusted():
            print('  Allow Accessibility and Input Monitoring for Sakura/Python in macOS Settings to enable Ctrl+Shift+T.')
            return None
        from pynput.keyboard import GlobalHotKeys
        listener = GlobalHotKeys({shortcut: callback})
        listener.start()
        listener.wait()
        return listener if listener.is_alive() else None
    except Exception as exc:
        print(f'  macOS global shortcut unavailable: {exc}')
        return None


def foreground_game():
    from AppKit import NSWorkspace
    from game_detection import classify_game
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None or app.processIdentifier() == os.getpid():
        return {'detected': False, 'name': ''}
    url = app.executableURL()
    path = str(url.path()) if url else ''
    return {'detected': classify_game(path), 'name': str(app.localizedName() or ''),
            'pid': int(app.processIdentifier())}
