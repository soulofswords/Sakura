import unittest

from nvidia_ar_tracker import AR_EXPRESSION_NAMES, NvidiaARFaceTracker


class NvidiaARTrackerTests(unittest.TestCase):
    def test_expression_layout_includes_independent_cheek_puff_channels(self):
        self.assertEqual(len(AR_EXPRESSION_NAMES), 53)
        self.assertIn('CheekPuff_L', AR_EXPRESSION_NAMES)
        self.assertIn('CheekPuff_R', AR_EXPRESSION_NAMES)
        self.assertLess(AR_EXPRESSION_NAMES.index('CheekPuff_L'), AR_EXPRESSION_NAMES.index('CheekPuff_R'))

    def test_recent_frame_is_not_proof_of_face_and_stale_face_expires(self):
        import time
        tracker=NvidiaARFaceTracker()
        tracker._updated_at=time.monotonic()
        tracker._result={'JawOpen':.7}
        self.assertTrue(tracker.snapshot()['connected'])
        self.assertFalse(tracker.snapshot()['face_detected'])
        self.assertEqual(tracker.snapshot()['blendshapes'],{})
        tracker._face_detected=True
        self.assertTrue(tracker.snapshot()['face_detected'])
        self.assertEqual(tracker.snapshot()['blendshapes']['jawOpen'],.7)
        tracker._updated_at=time.monotonic()-.4
        self.assertFalse(tracker.snapshot()['face_detected'])
        self.assertEqual(tracker.snapshot()['blendshapes'],{})

    def test_frame_input_is_refused_when_tracker_is_disabled(self):
        tracker = NvidiaARFaceTracker()
        with self.assertRaisesRegex(RuntimeError, 'not enabled'):
            tracker.submit_frame(b'jpeg', 640, 480)

    def test_frame_size_and_payload_are_validated_before_queueing(self):
        tracker = NvidiaARFaceTracker()
        tracker._thread = type('RunningThread', (), {'is_alive': lambda self: True})()
        for payload, width, height in ((b'x', 640, 480), (b'jpeg', 0, 480), (b'jpeg', 640, 1081)):
            with self.assertRaises(ValueError):
                tracker.submit_frame(payload, width, height)


    def test_equal_size_frames_rebind_cpu_buffer_before_every_transfer(self):
        import ctypes as C
        import numpy as np
        from nvidia_ar_tracker import _NvidiaExpressionSession, _NvCVImage
        session = object.__new__(_NvidiaExpressionSession)
        session.cpu_image = _NvCVImage()
        session.gpu_image = _NvCVImage()
        session._gpu_allocated = False
        session._frame_dims = None
        session.handle = C.c_void_p()
        session.intrinsics = [0, 0, 0]
        session.expressions = [0.0] * 53
        bound = []
        transferred = []
        session._image_init = lambda *args: bound.append(args[4].value) or 0
        session._image_alloc = lambda *args: 0
        session._set_object = lambda *args: 0
        session._image_transfer = lambda *args: transferred.append(bound[-1]) or 0
        session._run = lambda *args: 0
        frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(3)]
        for frame in frames:
            session.infer(frame)
        self.assertEqual(bound, [frame.ctypes.data for frame in frames])
        self.assertEqual(transferred, bound)


if __name__ == '__main__':
    unittest.main()
