"""Direct NVIDIA AR SDK facial-expression tracking for Sakura.

Frames come from Sakura's already-authorized browser camera stream.  This keeps
camera selection and consent in Sakura while the NVIDIA SDK performs local RTX
expression inference.  The SDK and model files are loaded from the user's
installed SDK directory and are never bundled or downloaded by this module.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import threading
import time
from io import BytesIO


AR_EXPRESSION_NAMES = (
    'BrowDown_L','BrowDown_R','BrowInnerUp_L','BrowInnerUp_R','BrowOuterUp_L','BrowOuterUp_R',
    'CheekPuff_L','CheekPuff_R','CheekSquint_L','CheekSquint_R','EyeBlink_L','EyeBlink_R',
    'EyeLookDown_L','EyeLookDown_R','EyeLookIn_L','EyeLookIn_R','EyeLookOut_L','EyeLookOut_R',
    'EyeLookUp_L','EyeLookUp_R','EyeSquint_L','EyeSquint_R','EyeWide_L','EyeWide_R',
    'JawForward','JawLeft','JawOpen','JawRight','MouthClose','MouthDimple_L','MouthDimple_R',
    'MouthFrown_L','MouthFrown_R','MouthFunnel','MouthLeft','MouthLowerDown_L','MouthLowerDown_R',
    'MouthPress_L','MouthPress_R','MouthPucker','MouthRight','MouthRollLower','MouthRollUpper',
    'MouthShrugLower','MouthShrugUpper','MouthSmile_L','MouthSmile_R','MouthStretch_L','MouthStretch_R',
    'MouthUpperUp_L','MouthUpperUp_R','NoseSneer_L','NoseSneer_R',
)


def expression_aliases(values):
    result=dict(values)
    for name,value in values.items():
        base=name[:-2] if name.endswith(('_L','_R')) else name
        suffix='Left' if name.endswith('_L') else 'Right' if name.endswith('_R') else ''
        result[base[0].lower()+base[1:]+suffix]=value
    for name in ('BrowInnerUp','CheekPuff'):
        if name+'_L' in values and name+'_R' in values:
            result[name[0].lower()+name[1:]]=(values[name+'_L']+values[name+'_R'])*.5
    return result


class _NvCVImage(C.Structure):
    _fields_ = [
        ('width', C.c_uint), ('height', C.c_uint), ('pitch', C.c_int),
        ('pixelFormat', C.c_int), ('componentType', C.c_int),
        ('pixelBytes', C.c_ubyte), ('componentBytes', C.c_ubyte),
        ('numComponents', C.c_ubyte), ('planar', C.c_ubyte),
        ('gpuMem', C.c_ubyte), ('colorspace', C.c_ubyte),
        ('reserved', C.c_ubyte * 2), ('pixels', C.c_void_p),
        ('deletePtr', C.c_void_p), ('deleteProc', C.c_void_p),
        ('bufferBytes', C.c_ulonglong),
    ]


class _Point2f(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float)]


class _Point3f(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float), ('z', C.c_float)]


class _Quaternion(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float), ('z', C.c_float), ('w', C.c_float)]


class _Vector3f(C.Structure):
    _fields_ = [('vec', C.c_float * 3)]


class _Rect(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float), ('width', C.c_float), ('height', C.c_float)]


class _BoundingBoxes(C.Structure):
    _fields_ = [('boxes', C.POINTER(_Rect)), ('num_boxes', C.c_ubyte), ('max_boxes', C.c_ubyte)]


class _NvidiaExpressionSession:
    def __init__(self, sdk_root: Path):
        if os.name != 'nt':
            raise RuntimeError('Direct NVIDIA AR tracking is available only on Windows.')
        self.sdk_root = sdk_root
        self._dll_dirs = []  # Keep DLL search handles alive for the session.
        for directory in (
            sdk_root / 'bin',
            sdk_root / 'features' / 'nvarfaceexpressions' / 'bin',
            sdk_root / 'features' / 'nvarlandmarkdetection' / 'bin',
            sdk_root / 'features' / 'nvarfaceboxdetection' / 'bin',
        ):
            if directory.is_dir():
                self._dll_dirs.append(os.add_dll_directory(str(directory)))
        self._core = C.WinDLL(str(sdk_root / 'bin' / 'nvARPose.dll'))
        self._images = C.WinDLL(str(sdk_root / 'bin' / 'NVCVImage.dll'))
        self._bind_api()
        self.handle = C.c_void_p()
        self._check(self._create(b'FaceExpressions', C.byref(self.handle)), 'Create face-expression tracker')
        self.cpu_image = _NvCVImage()
        self.gpu_image = _NvCVImage()
        self._gpu_allocated = False
        self._loaded = False
        self._frame_dims = None
        try:
            self._set_string(self.handle, b'NvAR_Parameter_Config_ModelDir', str(sdk_root / 'bin' / 'models').encode())
            self._set_string(self.handle, b'NvAR_Parameter_Config_ModelCacheDir', str(sdk_root / 'bin' / 'models' / 'cache').encode())
            self._check(self._set_u32(self.handle, b'NvAR_Parameter_Config_Temporal', 55), 'Set temporal filtering')
            self._check(self._set_u32(self.handle, b'NvAR_Parameter_Config_PoseMode', 1), 'Set face pose mode')
            self._check(self._set_u32(self.handle, b'NvAR_Parameter_Config_EnableCheekPuff', 1), 'Enable cheek-puff tracking')
            self._check(self._load(self.handle), 'Load NVIDIA face-expression model')
            count = C.c_uint()
            self._check(self._get_u32(self.handle, b'NvAR_Parameter_Config_ExpressionCount', C.byref(count)), 'Read expression count')
            if count.value != len(AR_EXPRESSION_NAMES):
                raise RuntimeError(f'Unexpected NVIDIA AR expression count ({count.value}); expected {len(AR_EXPRESSION_NAMES)}.')
            self.expressions = (C.c_float * count.value)()
            self._check(self._set_f32_array(self.handle, b'NvAR_Parameter_Output_ExpressionCoefficients', self.expressions, count.value), 'Set expression output')
            # NVIDIA's sample app binds these SDK outputs before inference;
            # the face-expression feature requires them even when Sakura only
            # consumes the expression coefficients.
            self._boxes_data = (_Rect * 25)()
            self._boxes = _BoundingBoxes(self._boxes_data, 0, len(self._boxes_data))
            self._check(self._set_object(self.handle, b'NvAR_Parameter_Output_BoundingBoxes',
                                         C.cast(C.byref(self._boxes), C.c_void_p), C.sizeof(_BoundingBoxes)), 'Set face-box output')
            self._landmarks = (_Point2f * 126)()
            self._check(self._set_object(self.handle, b'NvAR_Parameter_Output_Landmarks',
                                         C.cast(self._landmarks, C.c_void_p), C.sizeof(_Point2f)), 'Set landmark output')
            self._landmarks3d = (_Point3f * 126)()
            self._check(self._set_object(self.handle, b'NvAR_Parameter_Output_Landmarks3d',
                                         C.cast(self._landmarks3d, C.c_void_p), C.sizeof(_Point3f)), 'Set 3D landmark output')
            self._landmark_confidence = (C.c_float * 126)()
            self._check(self._set_f32_array(self.handle, b'NvAR_Parameter_Output_LandmarksConfidence',
                                            self._landmark_confidence, len(self._landmark_confidence)), 'Set landmark confidence output')
            self._pose = _Quaternion()
            self._pose_translation = _Vector3f()
            self._check(self._set_object(self.handle, b'NvAR_Parameter_Output_Pose',
                                         C.cast(C.byref(self._pose), C.c_void_p), C.sizeof(_Quaternion)), 'Set face-pose output')
            self._check(self._set_object(self.handle, b'NvAR_Parameter_Output_PoseTranslation',
                                         C.cast(C.byref(self._pose_translation), C.c_void_p), C.sizeof(_Vector3f)), 'Set face-pose translation output')
            self.intrinsics = (C.c_float * 3)()
            self._check(self._set_f32_array(self.handle, b'NvAR_Parameter_Input_CameraIntrinsicParams', self.intrinsics, 3), 'Set camera intrinsics')
            self._loaded = True
        except Exception:
            self.close()
            raise

    @staticmethod
    def _check(code, operation):
        if int(code) != 0:
            raise RuntimeError(f'{operation} failed with NVIDIA AR SDK status {int(code)}.')

    def _bind_api(self):
        ptr, uint, sint, ulong = C.c_void_p, C.c_uint, C.c_int, C.c_ulong
        def bind(library, name, result, args):
            fn = getattr(library, name)
            fn.restype, fn.argtypes = result, args
            return fn
        self._create = bind(self._core, 'NvAR_Create', sint, [C.c_char_p, C.POINTER(ptr)])
        self._destroy = bind(self._core, 'NvAR_Destroy', sint, [ptr])
        self._set_string = bind(self._core, 'NvAR_SetString', sint, [ptr, C.c_char_p, C.c_char_p])
        self._set_u32 = bind(self._core, 'NvAR_SetU32', sint, [ptr, C.c_char_p, uint])
        self._get_u32 = bind(self._core, 'NvAR_GetU32', sint, [ptr, C.c_char_p, C.POINTER(uint)])
        self._set_object = bind(self._core, 'NvAR_SetObject', sint, [ptr, C.c_char_p, ptr, ulong])
        self._set_f32_array = bind(self._core, 'NvAR_SetF32Array', sint, [ptr, C.c_char_p, C.POINTER(C.c_float), sint])
        self._load = bind(self._core, 'NvAR_Load', sint, [ptr])
        self._run = bind(self._core, 'NvAR_Run', sint, [ptr])
        self._image_init = bind(self._images, 'NvCVImage_Init', sint,
                                [C.POINTER(_NvCVImage), uint, uint, sint, ptr, sint, sint, uint, uint])
        self._image_alloc = bind(self._images, 'NvCVImage_Alloc', sint,
                                 [C.POINTER(_NvCVImage), uint, uint, sint, sint, uint, uint, uint])
        self._image_transfer = bind(self._images, 'NvCVImage_Transfer', sint,
                                    [C.POINTER(_NvCVImage), C.POINTER(_NvCVImage), C.c_float, ptr, ptr])
        self._image_dealloc = bind(self._images, 'NvCVImage_Dealloc', None, [C.POINTER(_NvCVImage)])

    def infer(self, frame_bgr):
        import numpy as np
        height, width = frame_bgr.shape[:2]
        if self._frame_dims != (width, height):
            if self._gpu_allocated:
                self._image_dealloc(C.byref(self.gpu_image))
                self.gpu_image = _NvCVImage()
                self._gpu_allocated = False
            self._check(self._image_alloc(C.byref(self.gpu_image), width, height, 5, 1, 0, 1, 1), 'Allocate RTX frame')
            self._gpu_allocated = True
            self._check(self._set_object(self.handle, b'NvAR_Parameter_Input_Image',
                                         C.cast(C.byref(self.gpu_image), C.c_void_p), C.sizeof(_NvCVImage)), 'Set tracker input image')
            self.intrinsics[:] = (float(height), float(width) / 2.0, float(height) / 2.0)
            self._frame_dims = (width, height)
        # Every JPEG decode owns a new NumPy buffer, including equal-size frames.
        # Rebind the host pointer before every transfer; the previous buffer may
        # already have been freed. Only the GPU allocation is reusable.
        self._check(self._image_init(C.byref(self.cpu_image), width, height, int(frame_bgr.strides[0]),
                                     C.c_void_p(frame_bgr.ctypes.data), 5, 1, 0, 0), 'Set webcam frame')
        self._check(self._image_transfer(C.byref(self.cpu_image), C.byref(self.gpu_image), 1.0, None, None), 'Transfer camera frame to RTX')
        self._check(self._run(self.handle), 'Run NVIDIA face-expression inference')
        return {name: max(0.0, min(1.0, float(self.expressions[index])))
                for index, name in enumerate(AR_EXPRESSION_NAMES)}

    def close(self):
        if getattr(self, '_gpu_allocated', False):
            self._image_dealloc(C.byref(self.gpu_image))
            self._gpu_allocated = False
        if getattr(self, 'handle', None) and self.handle.value:
            self._destroy(self.handle)
            self.handle = C.c_void_p()
        self._loaded = False


class NvidiaARFaceTracker:
    """Single-session, latest-frame worker around NVIDIA AR SDK inference."""
    def __init__(self):
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self._frame = None
        self._result = {}
        self._updated_at = 0.0
        self._error = ''
        self._root = None
        self._fps = 0

    def start(self, sdk_root: str):
        root = Path(sdk_root).expanduser().resolve()
        if root.name.lower() != 'arsdk' and (root / 'ARSDK').is_dir():
            root = root / 'ARSDK'
        if not (root / 'bin' / 'nvARPose.dll').is_file():
            raise ValueError(f'NVIDIA AR SDK Core was not found in {root}. Choose the ARSDK folder or its parent folder.')
        if self._thread and self._thread.is_alive():
            if self._root == root and not self._error:
                return self.snapshot()
            self.stop()
        self._root = root
        self._error = ''
        self._frame = None
        self._result = {}
        self._updated_at = 0.0
        self._fps = 0
        self._ready.clear()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='SakuraNvidiaARFaceTracker', daemon=True)
        self._thread.start()
        if not self._ready.wait(45):
            self.stop()
            raise RuntimeError('NVIDIA AR SDK initialization timed out. Check the SDK feature packages and NVIDIA driver.')
        if self._error:
            raise RuntimeError(self._error)
        return self.snapshot()

    def submit_frame(self, jpeg: bytes, width: int, height: int):
        if not self._thread or not self._thread.is_alive() or self._error:
            raise RuntimeError(self._error or 'NVIDIA RTX tracking is not enabled.')
        if not (1 <= width <= 1920 and 1 <= height <= 1080 and 4 <= len(jpeg) <= 2_500_000):
            raise ValueError('Invalid or oversized NVIDIA tracking frame.')
        with self._lock:
            self._frame = (bytes(jpeg), int(width), int(height))
        self._wake.set()

    def snapshot(self):
        with self._lock:
            age = time.monotonic() - self._updated_at if self._updated_at else None
            return {
                'running': bool(self._thread and self._thread.is_alive() and not self._error),
                'connected': age is not None and age < 1.5,
                'age_ms': round(age * 1000) if age is not None else None,
                'fps': self._fps,
                'blendshapes': expression_aliases(self._result) if age is not None and age < 1.5 else {},
                'error': self._error,
                'sdk': str(self._root) if self._root else '',
            }

    def stop(self):
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=8)
        self._thread = None
        self._frame = None
        self._result = {}
        self._updated_at = 0.0

    def _run(self):
        session = None
        try:
            session = _NvidiaExpressionSession(self._root)
            self._ready.set()
            count, started = 0, time.monotonic()
            while not self._stop.is_set():
                self._wake.wait(1.0)
                self._wake.clear()
                if self._stop.is_set():
                    break
                with self._lock:
                    frame = self._frame
                    self._frame = None
                if frame is None:
                    continue
                jpeg, width, height = frame
                from PIL import Image
                import numpy as np
                with Image.open(BytesIO(jpeg)) as decoded:
                    rgb = decoded.convert('RGB')
                    if rgb.size != (width, height):
                        raise ValueError('Tracking frame dimensions did not match its image data.')
                    frame_bgr = np.ascontiguousarray(np.asarray(rgb)[:, :, ::-1])
                result = session.infer(frame_bgr)
                count += 1
                now = time.monotonic()
                with self._lock:
                    self._result = result
                    self._updated_at = now
                    if now - started >= 1.0:
                        self._fps = round(count / (now - started))
                        count, started = 0, now
        except Exception as error:
            self._error = f'NVIDIA RTX face tracker stopped: {error}'
        finally:
            self._ready.set()
            if session:
                session.close()


tracker = NvidiaARFaceTracker()
