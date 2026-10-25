"""Avatar output through Sakura's dedicated virtual-camera device."""
import queue
import time

from spout_output import SpoutOutput


def camera_frame(pixels, width, height):
    import numpy as np
    from PIL import Image
    image = Image.frombytes('RGBA', (width, height), pixels)
    image.thumbnail((1280, 720), Image.Resampling.BILINEAR)
    background = Image.new('RGBA', (1280, 720), (16, 18, 28, 255))
    background.alpha_composite(image, ((1280-image.width)//2, (720-image.height)//2))
    return np.asarray(background.convert('RGB')).copy()


class VirtualCamera(SpoutOutput):
    def status(self):
        return {**super().status(), 'device': 'Sakura Virtual Camera'}

    def _run(self):
        camera = None
        try:
            import numpy as np
            from sakura_camera_native import NativeCamera
            camera = NativeCamera(width=1280, height=720, fps=30)
            self.device = camera.device
            self.enabled = True
            self.ready.set()
            latest = np.zeros((720, 1280, 3), dtype=np.uint8)
            while not self.stop_event.is_set():
                try:
                    pixels, width, height = self.frames.get_nowait()
                    latest = camera_frame(pixels, width, height)
                except queue.Empty:
                    if time.monotonic()-self.last_frame > 15:
                        self.error = 'Virtual camera stopped because avatar frames stopped arriving.'
                        break
                camera.send(latest)
                self.sent += 1
                self.stop_event.wait(1/30)
        except Exception as error:
            self.error = 'Sakura Virtual Camera could not start. ' + str(error)
        finally:
            if camera:
                camera.close()
            self.enabled = False
            self.ready.set()


output = VirtualCamera()
