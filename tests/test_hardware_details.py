from unittest.mock import patch
import hardware_details as details

TEACHER={'conversation_mode':'teacher','computer_control_enabled':True,'computer_access_level':'restricted'}


def test_hardware_questions_are_routed_without_guessing():
    for text,kind in [('can u tell me cpu temp and watts','cpu'),('can u tell me temp of gpu','gpu'),('how much ram is being used','ram'),('which processes are consuming most resources','processes')]:
        assert details.question(text)==kind
    assert details.question('kill high usage processes') is None
    assert details.question('I like graphics cards') is None
    assert details.question('tell me watts of each component')=='all'
    assert details.question('cpu and gpu temperature')=='all'


def test_permissions_and_teacher_required_before_sampling():
    with patch.object(details,'process_usage') as inspect:
        assert 'Full access' in details.answer('top processes usage',TEACHER)['reply']
        assert 'Enable Computer access' in details.answer('cpu temp',{**TEACHER,'computer_control_enabled':False})['reply']
        assert details.answer('cpu temp',{**TEACHER,'conversation_mode':'friend'})['mode_required']=='teacher'
        inspect.assert_not_called()


def test_sensor_readings_and_unavailable_sensors_are_honest():
    with patch('system_tools.system_status',return_value={'cpu_percent':12,'gpus':[{'name':'GPU','temperature_c':53,'power_watts':80,'utilization_percent':20}]}),patch.object(details,'cpu_sensors',return_value=[]):
        assert 'CPU temperature is unavailable' in details.answer('cpu temperature',TEACHER)['reply']
        gpu=details.answer('gpu watts',TEACHER)['reply']
        assert '53°C' in gpu and '80 W' in gpu


def test_full_access_reports_processes_without_ending_anything():
    data={'top_cpu':[{'name':'app.exe','pid':42,'cpu_percent':20}],'top_ram':[{'name':'app.exe','pid':42,'ram_bytes':1024**3}]}
    with patch.object(details,'process_usage',return_value=data):
        result=details.answer('which processes use most resources',{**TEACHER,'computer_access_level':'full'})
        assert 'app.exe' in result['reply'] and 'Nothing was stopped' in result['reply']


def test_chat_keeps_phone_permission_and_returns_measured_reply():
    import app
    from local_client import TestClient
    with patch.object(app,'get_settings',return_value=TEACHER),patch.object(app,'llm',None),patch.object(app.app.state,'tracking_only',False,create=True),patch('system_tools.system_status',return_value={'ram':{'used_bytes':1024**3,'total_bytes':2*1024**3,'percent':50}}):
        client=TestClient(app.app)
        result=client.post('/api/chat',json={'text':'how much ram is being used'}).json()
        assert '1.0 of 2.0 GB' in result['reply']
        phone=client.post('/api/chat',json={'text':'how much ram is being used','phone':True}).json()
        assert 'Enable Computer access' in phone['reply']


def test_access_level_setting_rejects_unknown_permission():
    import app
    from local_client import TestClient
    with patch.object(app,'_started_locally',return_value=True),patch.object(app,'save_settings') as save:
        result=TestClient(app.app).post('/api/settings',json={'computer_access_level':'admin'})
        assert result.status_code==400
        save.assert_not_called()
