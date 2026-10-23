"""Avatar output through an installed OBS virtual camera driver."""
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
        return {**super().status(), 'device': getattr(self, 'device', 'OBS Virtual Camera')}

    def _run(self):
        camera = None
        try:
            import numpy as np
            import pyvirtualcam
            camera = pyvirtualcam.Camera(width=1280, height=720, fps=30,
                                         fmt=pyvirtualcam.PixelFormat.RGB, backend='obs')
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
                camera.sleep_until_next_frame()
        except Exception as error:
            self.error = ('Virtual camera could not start. Install OBS Studio with its virtual camera driver, '
                          'and stop Virtual Camera in OBS before enabling it in Sakura. ' + str(error))
        finally:
            if camera:
                camera.close()
            self.enabled = False
            self.ready.set()


output = VirtualCamera()
