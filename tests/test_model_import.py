import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from model_import import import_package


def pmx_with_bones(names):
    import struct
    def i32(value): return struct.pack('<i', value)
    def text(value=''):
        encoded = value.encode('utf-8')
        return i32(len(encoded)) + encoded
    data = bytearray(b'PMX ' + struct.pack('<f', 2.1) + bytes([8, 1, 0, 1, 1, 1, 1, 1, 1]))
    data += text() * 4
    data += i32(0) * 4  # vertices, faces, textures, materials
    data += i32(len(names))
    for index, name in enumerate(names):
        data += text(name) + text()
        data += struct.pack('<3f', 0.0, float(index), 0.0)
        data += struct.pack('<b', -1 if index == 0 else 0) + i32(0) + struct.pack('<H', 0)
        data += struct.pack('<3f', 0.0, 0.1, 0.0)
    return bytes(data)


class ModelImportTests(unittest.TestCase):
    def test_zip_keeps_texture_structure(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('Character/model.pmx', pmx_with_bones(['全ての親', 'センター', '上半身', '頭', '左腕', '右腕', '左足', '右足']))
            archive.writestr('Character/tex/skin.png', b'texture')
        with tempfile.TemporaryDirectory() as folder:
            result = import_package(folder, [('character.zip', data.getvalue())])
            self.assertTrue(result['models'][0].startswith('pmx/'))
            model = Path(folder) / result['models'][0]
            self.assertTrue(model.is_file())
            self.assertEqual((model.parent / 'tex/skin.png').read_bytes(), b'texture')

    def test_non_humanoid_pmx_is_rejected_before_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'humanoid skeleton'):
                import_package(folder, [('creature.pmx', pmx_with_bones(['root', 'head', 'tail']))])
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_invalid_package_does_not_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ['../model.pmx', 'model.pmx']:
                with self.assertRaises(ValueError):
                    import_package(folder, [(name, b'invalid')])
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_live2d_import_checks_required_assets_and_saves_separately(self):
        import json
        files = [('Miku/avatar.model3.json', json.dumps({'FileReferences': {'Moc': 'avatar.moc3', 'Textures': ['textures/skin.png']}}).encode()), ('Miku/avatar.moc3', b'MOC3'+bytes(8)), ('Miku/textures/skin.png', b'texture')]
        with tempfile.TemporaryDirectory() as folder:
            result = import_package(folder, files, 'live2d')
            self.assertTrue(result['renderable'])
            self.assertIn('Live2D package imported', result['message'])
            self.assertTrue(result['models'][0].startswith('live2d/'))
            self.assertTrue((Path(folder)/result['models'][0]).is_file())
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'missing'):
                import_package(folder, files[:-1], 'live2d')
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_named_folders_add_id_only_on_collision_and_never_overwrite(self):
        files=[('Ringo.pmx',pmx_with_bones(['全ての親','センター','上半身','頭','左腕','右腕','左足','右足']))]
        with tempfile.TemporaryDirectory() as folder:
            first=import_package(folder,files,'pmx','Ananta / Ringo','cloud-first')
            same=import_package(folder,files,'pmx','Ananta / Ringo','cloud-second')
            self.assertTrue(same['already_installed'])
            self.assertEqual(first['models'],same['models'])
            second=import_package(folder,[*files,('variant.txt',b'different outfit package')],'pmx','Ananta / Ringo','cloud-second')
            self.assertEqual(Path(first['models'][0]).parts[1],'Ringo')
            self.assertEqual(Path(second['models'][0]).parts[1],'Ringo cloud-second')
            self.assertTrue((Path(folder)/first['models'][0]).is_file())
            self.assertTrue((Path(folder)/second['models'][0]).is_file())

    def test_unsafe_or_reserved_display_names_stay_in_format_directory(self):
        from model_import import model_folder_name
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ['../../escape','CON','NUL.txt','..','name:*?<>|','日本語モデル']:
                label=model_folder_name(root,'pmx',name)
                self.assertTrue((root/'pmx'/label).resolve().is_relative_to(root/'pmx'))
                self.assertNotEqual(label,'CON');self.assertNotEqual(label,'NUL.txt')

    def test_format_buttons_reject_wrong_model_type(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'matching'):
                import_package(folder, [('model.pmx', b'PMX '+bytes(5))], 'vrm')
            self.assertEqual(list(Path(folder).iterdir()), [])
