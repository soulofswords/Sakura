import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from model_library import ModelLibrary, library_url, router
from model_library_config import LIBRARY_URL
from planner_tool_catalog import planner_tools

ROOT=Path(__file__).resolve().parents[1]


class AccountBoundaryTests(unittest.TestCase):
    def test_credentials_and_saved_sessions_never_reach_a_substituted_host(self):
        with tempfile.TemporaryDirectory() as folder, patch('model_library.requests.post') as post, patch('model_library.requests.get') as get:
            app=FastAPI();app.include_router(router(folder,lambda request:True))
            with TestClient(app) as client:
                for host in ('https://example.org', LIBRARY_URL+'.evil.invalid', 'https://localhost.evil.invalid', 'http://localhost:9999', 'http://127.0.0.1:9999'):
                    for action in ('signin','signup','recover'):
                        response=client.post('/api/model-library/account/'+action,json={'url':host,'email':'user@example.com','password':'password-test'})
                        self.assertEqual(response.status_code,400)
                    config={'url':host,'token':'saved-access','refresh_token':'saved-refresh','expires_at':0}
                    with patch('agent_connections.secret_get',return_value=config):
                        self.assertEqual(client.get('/api/model-library/models').status_code,400)
                    with self.assertRaises(ValueError):ModelLibrary(folder,lambda:config).catalogue()
            post.assert_not_called();get.assert_not_called()

    def test_email_does_not_reveal_or_authorize_an_existing_reset_session(self):
        from model_library_confirm import hold,take,router as confirmation_router
        identifier=hold('mailbox-verified-session','user@example.com')
        try:
            with tempfile.TemporaryDirectory() as folder, patch('model_library.requests.post') as post:
                post.return_value.__enter__.return_value=Mock(status_code=400,json=lambda:{'error_code':'invalid_credentials'})
                app=FastAPI();app.include_router(router(folder,lambda request:True));app.include_router(confirmation_router(lambda request:True,lambda request:True))
                with TestClient(app) as client:
                    response=client.post('/api/model-library/account/signin',json={'email':'user@example.com','password':'incorrect-password'})
                    self.assertNotIn(identifier,response.text)
                    self.assertNotIn('reset_id',response.json())
                    response=client.post('/api/model-library/finish-reset',json={'email':'user@example.com','password':'new-password-123','confirm':'new-password-123'})
                    self.assertEqual(response.status_code,400)
                self.assertEqual(take(identifier)[0],'mailbox-verified-session')
        finally:take(identifier)


class PlannerAndRoutingTests(unittest.TestCase):
    def test_discovery_does_not_flood_the_planner_and_relevant_tools_remain(self):
        tools=[{'name':f'mcp.work.noise_{i}','description':'Unrelated metadata '*80,'inputSchema':{}} for i in range(500)]
        tools.append({'name':'mcp.work.create_calendar_event','description':'Create a calendar meeting','inputSchema':{}})
        selected=planner_tools(tools,'create calendar meeting')
        self.assertLessEqual(len(selected),80)
        self.assertLessEqual(len(json.dumps(selected,ensure_ascii=False).encode()),24000)
        self.assertIn('mcp.work.create_calendar_event',[tool['name'] for tool in selected])

    def test_background_steps_keep_the_phone_channel(self):
        import assistant_tools
        from assistant_commands import background_sequence
        with patch('assistant_commands.run_command',return_value='Opened.') as command:
            result=background_sequence('open calculator then open notepad',True,'Sakura','phone')
            deadline=time.monotonic()+3
            while assistant_tools.run_state(result['id'])['status']=='running' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(command.call_count,2)
            self.assertTrue(all(call.kwargs.get('channel')=='phone' for call in command.call_args_list))


class AndroidGatewayTests(unittest.TestCase):
    def test_actual_java_gateway_and_reply_encoding(self):
        cache=ROOT/'tools/android-cache'
        java=next((cache/'jdk').glob('*/bin/javac.exe'),None)
        platform=next((cache/'platform').glob('*/android.jar'),None)
        json_jar=cache/'security-test/json-20240303.jar'
        if not java or not platform or not json_jar.exists():self.skipTest('Android SDK/JDK and cached JSON test dependency required')
        harness='''package app.sakura.mobile;
import android.webkit.JavascriptInterface;import org.json.*;
public class GatewayProbe {
 public static class Target {
  int count;
  @JavascriptInterface public String echo(String text){count++;return text;}
  public String hidden(){throw new Error("Private method exposed");}
 }
 public static void main(String[] args)throws Exception{
  Target target=new Target();NativeGateway gateway=new NativeGateway(target);
  String bootstrap=gateway.bootstrap();
  java.util.regex.Matcher match=java.util.regex.Pattern.compile("proof=\\\"([^\\\"]+)\\\"").matcher(bootstrap);if(!match.find())throw new Error("Missing capability");String proof=match.group(1);
  if(!new JSONObject(gateway.invoke("wrong","echo","[\\\"secret\\\"]")).has("error")||target.count!=0)throw new Error("Capability bypass");
  if(!new JSONObject(gateway.invoke(proof,"hidden","[]")).has("error"))throw new Error("Unannotated method exposed");
  if(!new JSONObject(gateway.invoke(proof,"echo","[true]")).has("error"))throw new Error("Argument type bypass");
  if(!new JSONObject(gateway.invoke(proof,"echo","[\\\"valid\\\"]")).getString("value").equals("valid")||target.count!=1)throw new Error("Authorized bridge failed");
  JSONObject result=new JSONObject().put("bootstrap",bootstrap).put("invalidScript",NativeReplies.script("job","{});window.injected=true;//")).put("dataScript",NativeReplies.script("job","{\\\"text\\\":\\\"</script>);window.injected=true;\\\"}"));
  System.out.println(result);
 }
}'''
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);source=folder/'GatewayProbe.java';source.write_text(harness,encoding='utf-8')
            classpath=str(json_jar)+';'+str(platform)
            subprocess.run([str(java),'-encoding','UTF-8','-cp',classpath,'-d',str(folder),str(ROOT/'android/src/app/sakura/mobile/NativeGateway.java'),str(ROOT/'android/src/app/sakura/mobile/NativeReplies.java'),str(source)],check=True,capture_output=True)
            run=subprocess.run([str(java.with_name('java.exe')),'-cp',str(folder)+';'+classpath,'app.sakura.mobile.GatewayProbe'],check=True,capture_output=True,text=True,encoding='utf-8')
            proof=json.loads(run.stdout)
            self.assertIn('JSON.parse(',proof['invalidScript'])
            (cache/'security-test/gateway-proof.json').write_text(json.dumps(proof),encoding='utf-8')


if __name__=='__main__':unittest.main()
