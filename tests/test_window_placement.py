import tempfile
import unittest
from pathlib import Path
from window_placement import compact_geometry,read_placement,save_placement


class PlacementTests(unittest.TestCase):
    def test_default_bottom_right_avoids_taskbar(self):
        self.assertEqual(compact_geometry({'x':0,'y':0,'width':1920,'height':1032}),
                         {'x':1448,'y':260,'width':460,'height':760})

    def test_saved_drag_position_and_size_survive_reopen(self):
        saved={'x':140,'y':80,'width':470,'height':700}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'profile'/'placement.json'
            save_placement(path,saved)
            self.assertEqual(compact_geometry({'x':0,'y':0,'width':1920,'height':1032},read_placement(path)),saved)

    def test_second_monitor_and_removed_monitor(self):
        self.assertEqual(compact_geometry({'x':-1920,'y':0,'width':1920,'height':1032})['x'],-472)
        area={'x':0,'y':0,'width':1280,'height':720}
        bounds=compact_geometry(area,{'x':2000,'y':1200,'width':460,'height':760})
        self.assertEqual(bounds,{'x':820,'y':0,'width':460,'height':720})

    def test_invalid_saved_placement_uses_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'placement.json'
            for raw in ['null','[]','broken','{"x":true,"y":0,"width":460,"height":760}',
                        '{"x":0,"y":0,"width":-1,"height":760}']:
                path.write_text(raw)
                self.assertIsNone(read_placement(path))
