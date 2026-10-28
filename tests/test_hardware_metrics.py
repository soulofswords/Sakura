import unittest
from hardware_metrics import aggregate_gpu
from system_tools import status_reply
class MetricsTests(unittest.TestCase):
 def test_same_engine_processes_sum_but_different_engines_do_not(self):
  key='luid_0x00000000_0x00000001_phys_0'
  adapter={'name':'Test GPU','counter_key':key,'vram_total_bytes':8*1024**3}
  rows=aggregate_gpu([adapter],[('pid_1_'+key+'_eng_0_engtype_3D',20),('pid_2_'+key+'_eng_0_engtype_3D',20),('pid_3_'+key+'_eng_1_engtype_Copy',30)],[(key,2*1024**3)])
  self.assertEqual(rows[0]['utilization_percent'],40)
  self.assertEqual(rows[0]['vram_percent'],25)
 def test_unavailable_is_not_zero_and_invalid_values_are_ignored(self):
  adapter={'name':'Test GPU','counter_key':'luid_0x0_0x1_phys_0','vram_total_bytes':0}
  result=aggregate_gpu([adapter],[('pid_1_luid_0x0_0x1_phys_0_eng_0',float('nan'))],[])[0]
  self.assertIsNone(result['utilization_percent']);self.assertIsNone(result['vram_used_bytes']);self.assertIsNone(result['vram_percent'])
 def test_spoken_status_has_actual_cpu_gpu_ram_and_vram(self):
  data={'cpu_percent':13,'ram':{'total_bytes':32*1024**3,'used_bytes':8*1024**3,'percent':25},'disk':{'free_bytes':100*1024**3},'gpus':[{'name':'Example GPU','utilization_percent':40,'vram_used_bytes':2*1024**3,'vram_total_bytes':8*1024**3,'vram_percent':25}]}
  reply=status_reply(data)
  for value in ['CPU usage is 13 percent','Example GPU usage is 40 percent','RAM usage is 8.0 of 32.0 GB, 25 percent','VRAM usage is 2.0 of 8.0 GB, 25 percent']:self.assertIn(value,reply)
  data['gpus'][0]['utilization_percent']=None;data['gpus'][0]['vram_used_bytes']=None
  reply=status_reply(data);self.assertIn('usage is unavailable',reply);self.assertNotIn('usage is 0 percent',reply)
 def test_specs_are_spoken_when_present_and_optional_otherwise(self):
  data={'cpu_name':'Example CPU 9000','os':'Windows 11 (build 26200)','cpu_percent':13,'ram':{'total_bytes':32*1024**3,'used_bytes':8*1024**3,'percent':25},'disk':{'free_bytes':100*1024**3},'gpus':[]}
  self.assertIn('System: Example CPU 9000, Windows 11 (build 26200).',status_reply(data))
  data.pop('cpu_name');data.pop('os')
  self.assertNotIn('System:',status_reply(data))
 def test_spec_questions_reach_the_status_tool(self):
  from assistant_tools import classify
  for text in ['can u see my pc specs ?','Can you see my PC specs?','what are my pc specs','pc specs','system specifications','whats my processor','cpu model','graphics card','windows version','my hardware']:
   self.assertEqual(classify(text),('system.status',{}),text)
  for text in ['pc status','what is the pc status','tell me my ram usage','check battery level','free disk space']:
   self.assertEqual(classify(text),('system.status',{}),text)
  self.assertIsNone(classify('can you see my screen'))
if __name__=='__main__':unittest.main()
