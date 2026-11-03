import pytest
from agent_skills import AgentSkills
from agent_starter_skills import PACK,install,describe,learn_completed


def test_the_whole_pack_installs_once_and_requirements_visible(tmp_path):
    skills=AgentSkills(tmp_path/'skills.json');assert len(PACK)==28
    assert len(install(skills))==len(PACK);assert install(skills)==[]
    rows=describe(skills.list());assert len(rows)==len(PACK) and all(row['requirements'] for row in rows)
    assert 'macOS' in next(x for x in rows if x['name']=='find-my')['requirements']
    for row in rows:assert len(row['instructions'])<=4000 and 'approval' in row['instructions']


def test_learn_requires_success_and_never_copies_private_arguments(tmp_path):
    skills=AgentSkills(tmp_path/'skills.json');run={'status':'completed','steps':[{'status':'completed','tool':'files.read','arguments':{'path':'PRIVATE_PATH'},'result':{'ok':True,'text':'TOKEN_SECRET'}}]}
    item=learn_completed(skills,run,'my-workflow');assert 'files.read' in item['instructions'];assert 'PRIVATE_PATH' not in item['instructions'] and 'TOKEN_SECRET' not in item['instructions']
    run['steps'][0]['result']['ok']=False
    with pytest.raises(ValueError):learn_completed(skills,run,'bad-workflow')


def test_repair_skill_names_only_real_agent_tools():
    import re
    from agent_runtime import LOCAL_TOOLS
    available={tool['name'] for tool in LOCAL_TOOLS}
    named=set(re.findall(r'\bapp\.[a-z.]+',PACK['sakura-self-repair'][2]))
    assert {'app.diagnostics','app.source.patch','app.state.repair','app.files.sync','app.redeploy'} <= named
    assert named <= available


def test_starter_pack_never_overflows_or_replaces_a_full_user_library(tmp_path):
    skills=AgentSkills(tmp_path/'skills.json')
    for i in range(50):skills.save('custom-'+str(i),'Preserve this existing user procedure.')
    assert install(skills)==[] and len(skills.list())==50
