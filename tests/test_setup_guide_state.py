from setup_guide_state import seen

def test_seen_survives_reopening_and_editions_stay_separate(tmp_path):
    assert not seen(tmp_path, 'companion')
    assert seen(tmp_path, 'companion', True)
    assert seen(tmp_path, 'companion')
    assert not seen(tmp_path, 'vtuber')
    assert seen(tmp_path, 'vtuber', True)
    assert seen(tmp_path, 'companion')

def test_unknown_guide_does_not_create_a_file(tmp_path):
    import pytest
    with pytest.raises(ValueError):seen(tmp_path, '../../bad', True)
    assert not list(tmp_path.rglob('*.json'))
