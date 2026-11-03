import asyncio
from unittest.mock import Mock
import app

def test_emotion_setting_is_validated_and_saved(monkeypatch):
    monkeypatch.setattr(app,'_started_locally',lambda request:True)
    monkeypatch.setattr(app,'llm',None)
    settings={**app.get_settings(),'avatar_emotion':'auto'}
    monkeypatch.setattr(app,'get_settings',lambda:settings)
    save=Mock(side_effect=lambda data:{'avatar_emotion':'auto',**data})
    monkeypatch.setattr(app,'save_settings',save)
    invalid=asyncio.run(app.update_app_settings(None,{'avatar_emotion':'invented'}))
    assert invalid.status_code==400;save.assert_not_called()
    result=asyncio.run(app.update_app_settings(None,{'avatar_emotion':'concerned'}))
    assert result['settings']['avatar_emotion']=='concerned'
    assert save.call_args.args[0]['avatar_emotion']=='concerned'
