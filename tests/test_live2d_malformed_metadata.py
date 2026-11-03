import json
from live2d_expressions import discover_live2d_expressions


def test_non_object_model_settings_are_rejected(tmp_path):
    model = tmp_path / 'avatar.model3.json'
    model.write_text('[]')
    assert discover_live2d_expressions(model) == []


def test_malformed_optional_metadata_keeps_valid_expression(tmp_path):
    model = tmp_path / 'avatar.model3.json'
    model.write_text(json.dumps({'FileReferences': {'DisplayInfo': 'avatar.cdi3.json'}}))
    (tmp_path / 'avatar.cdi3.json').write_text('{"Parameters": null}')
    (tmp_path / 'avatar.vtube.json').write_text('[]')
    (tmp_path / 'broken.exp3.json').write_text('[]')
    (tmp_path / 'smile.exp3.json').write_text(json.dumps({'Type': 'Live2D Expression', 'Parameters': [None, {'Id': 'Smile', 'Value': 1}]}))
    assert discover_live2d_expressions(model) == [{'Name': 'smile', 'File': 'smile.exp3.json'}]


def test_malformed_references_are_ignored(tmp_path):
    model = tmp_path / 'avatar.model3.json'
    model.write_text('{"FileReferences": []}')
    assert discover_live2d_expressions(model) == []
