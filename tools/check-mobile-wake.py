"""Exercise actual Java wake phrase rules; verify the pinned optional pack/build contract."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

BASE=Path(__file__).resolve().parents[1]
java=next((BASE/'tools/android-cache/jdk').rglob('javac.exe')).parent
harness=r'''
package app.sakura.mobile;
public class WakeChecks {
 static void ok(boolean value,String label){if(!value)throw new AssertionError(label);}
 public static void main(String[] args){
  String phrase=WakePhrase.validate("Hey Sakura");ok(phrase.equals("hey sakura"),"Case normalization");
  ok(WakePhrase.matches("HEY, SAKURA!",phrase),"Punctuation normalization");
  ok(!WakePhrase.matches("hey sakura please",phrase),"Full phrase only");
  ok(!WakePhrase.matches("don't say hey sakura",phrase),"Unrelated leading speech");
  ok(!WakePhrase.matches("hey sakuramarie",phrase),"Word boundaries");
  ok(WakePhrase.trimCommand("hey sakura what time is it",phrase).equals("what time is it"),"Strip wake prefix");
  ok(WakePhrase.trimCommand("hey sakura",phrase).isEmpty(),"No fabricated question");
  ok(WakePhrase.confident("hey sakura",phrase,new double[]{.99,.98},1.2),"Completed confident phrase accepted");
  ok(!WakePhrase.confident("hey sakura",phrase,new double[]{.99,.4},1.2),"Low confidence rejected");
  ok(!WakePhrase.confident("huh",phrase,new double[]{.99},.8),"Unrelated speech rejected");
  ok(!WakePhrase.confident("hey sakura",phrase,new double[]{.99,.99},.1),"Short noise rejected");
  ok(!WakePhrase.confident("hey sakura",phrase,new double[]{},1),"No word evidence rejected");
  ok(!WakePhrase.meaningfulCommand("huh"),"Exact screenshot filler discarded");
  ok(!WakePhrase.meaningfulCommand("um uh hmm"),"Filler-only sequence discarded");
  ok(WakePhrase.meaningfulCommand("hello"),"Intentional greeting kept");
  ok(WakePhrase.meaningfulCommand("what time is it"),"Question kept");
  ok(WakePhrase.validate("hello computer").equals("hello computer"),"Custom phrase");
  for(String invalid:new String[]{"hello","hey 123","","one two three four five six seven","hey <script>"}){
   boolean rejected=false;try{WakePhrase.validate(invalid);}catch(IllegalArgumentException e){rejected=true;}ok(rejected,"Reject invalid phrase: "+invalid);
  }
 }
}
'''
with tempfile.TemporaryDirectory(prefix='sakura-wake-') as temp:
    out=Path(temp);source=out/'WakeChecks.java';source.write_text(harness,encoding='utf-8')
    subprocess.run([java/'javac.exe','-encoding','UTF-8','-d',out,BASE/'android/src/app/sakura/mobile/WakePhrase.java',source],check=True)
    subprocess.run([java/'java.exe','-cp',out,'app.sakura.mobile.WakeChecks'],check=True)
manifest=(BASE/'android/AndroidManifest.xml').read_text(encoding='utf-8')
assert 'android:foregroundServiceType="microphone"' in manifest and 'android:exported="false"' in manifest
assert 'android.permission.FOREGROUND_SERVICE_MICROPHONE' in manifest
assert 'BOOT_COMPLETED' not in manifest, 'No prohibited microphone start at boot'
service=(BASE/'android/src/app/sakura/mobile/WakeService.java').read_text(encoding='utf-8')
assert 'START_NOT_STICKY' in service and 'Stop listening' in service
assert 'MODE_IN_COMMUNICATION' in service and 'paused()' in service
assert 'MainActivity.deliverWakeCommand' in service
pack=BASE/'tools/android-cache/wake-deps/model.zip'
if pack.exists():assert hashlib.sha256(pack.read_bytes()).hexdigest()=='30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498'
print('PASS: actual Java default/custom wake phrase validation, word boundaries, no empty question, opt-in service/notification/no-boot-start contract and pinned pack integrity')
