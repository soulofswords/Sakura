import json
import struct
import unittest

from model_rig_validation import humanoid_bone_groups, validate_humanoid_names, validate_vrm_glb


class HumanoidValidationTests(unittest.TestCase):
    def test_japanese_chinese_and_english_bone_names(self):
        samples = [
            ['センター', '上半身', '頭', '左腕', '右腕', '左足', '右足'],
            ['髋骨', '上身', '头', '左上臂', '右上臂', '左大腿', '右大腿'],
            ['mixamorig:Hips', 'mixamorig:Spine', 'mixamorig:Head', 'mixamorig:LeftArm',
             'mixamorig:RightArm', 'mixamorig:LeftLeg', 'mixamorig:RightLeg'],
        ]
        for names in samples:
            with self.subTest(names=names):
                validate_humanoid_names(names)

    def test_non_humanoid_names_return_clear_error(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            validate_humanoid_names(['root', 'head', 'tail'], 'Creature.pmx')

    def test_vrm_glb_requires_humanoid_bone_metadata(self):
        bones = {name: {'node': i} for i, name in enumerate(
            ['hips', 'spine', 'head', 'leftUpperArm', 'rightUpperArm', 'leftUpperLeg', 'rightUpperLeg'])}
        document = {'extensions': {'VRMC_vrm': {'humanoid': {'humanBones': bones}}}}
        payload = json.dumps(document, separators=(',', ':')).encode('utf-8')
        payload += b' ' * (-len(payload) % 4)
        glb = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(payload)) + struct.pack('<II', len(payload), 0x4E4F534A) + payload
        validate_vrm_glb(glb)

    def test_legacy_vrm_list_and_invalid_node_references(self):
        names=['hips','spine','head','leftUpperArm','rightUpperArm','leftUpperLeg','rightUpperLeg']
        def pack(document):
            payload=json.dumps(document).encode('utf-8');payload+=b' '*(-len(payload)%4)
            return b'glTF'+struct.pack('<II',2,20+len(payload))+struct.pack('<II',len(payload),0x4E4F534A)+payload
        bones=[{'bone':name,'node':i} for i,name in enumerate(names)]
        document={'nodes':[{} for _ in names],'extensions':{'VRM':{'humanoid':{'humanBones':bones}}}}
        validate_vrm_glb(pack(document),'Legacy avatar')
        bones[0]['node']=99
        with self.assertRaisesRegex(ValueError,'invalid node reference'):
            validate_vrm_glb(pack(document))
        bones[0]['node']=True
        with self.assertRaisesRegex(ValueError,'invalid node reference'):
            validate_vrm_glb(pack(document))
        document['extensions']['VRM']['humanoid']['humanBones']={}
        with self.assertRaisesRegex(ValueError,'VRM 0 humanoid'):
            validate_vrm_glb(pack(document))
        document['extensions']={'VRMC_vrm':{'humanoid':{'humanBones':bones}}}
        with self.assertRaisesRegex(ValueError,'VRM 1 humanoid'):
            validate_vrm_glb(pack(document))


if __name__ == '__main__':
    unittest.main()
