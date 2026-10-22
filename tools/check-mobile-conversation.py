"""Exercise mobile conversation guards as compiled Java without API calls."""
from pathlib import Path
import subprocess,tempfile
BASE=Path(__file__).resolve().parents[1]
java=next((BASE/'tools/android-cache/jdk').rglob('javac.exe')).parent
source=r"""
package app.sakura.mobile;
import java.util.*;
public class ConversationChecks{
 static void require(boolean ok,String label){if(!ok)throw new AssertionError(label);}
 public static void main(String[] args){
 String bad="Oh, I see! You're asking about the character's bust size? That's a great question, Sakura can definitely help. What kind of things are you thinking about?";
 require(PhoneConversation.bad(bad,"Please answer",Arrays.asList(bad)),"evasive/repeated answer rejected");
 String answer="The update is still downloading. Wait for the progress indicator to finish before restarting the application.";
 require(PhoneConversation.bad(answer,"Is it done?",Arrays.asList(answer)),"cross-turn repetition");
 require(!PhoneConversation.bad(answer,"Say that again",Arrays.asList(answer)),"explicit requested repetition");
 require(!PhoneConversation.bad("Yes, it is.","Is it done?",Arrays.asList("Yes, it is.")),"short normal acknowledgment");
 require(PhoneConversation.common("appko hindi ati hai").contains("हिंदी"),"Romanized Hindi");
 require(PhoneConversation.common("app ladke ho kya ladki").contains("एआई"),"avatar identity");
 require(PhoneConversation.garbled("सरल बातचीत के लिए आपका सहमति है।"),"reported garbled Hindi");
 require(PhoneConversation.unsupportedLore("My friend Agent V runs a vending machine.","Who is Agent V?"),"invented friend");
 require(!PhoneConversation.unsupportedLore("My friend Agent V runs a vending machine.","Write a story about Agent V"),"explicit fiction allowed");
 require(PhoneConversation.spoken("Hello 👋🏽 Sir 🌸").equals("Hello  Sir"),"emoji sequences omitted from speech");
 System.out.println("PASS: actual Java cross-turn repetition, filler, common Hindi, invented lore and speech emoji guards");
 }}
"""
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);check=root/'ConversationChecks.java';check.write_text(source,encoding='utf-8')
 subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(root),str(BASE/'android/src/app/sakura/mobile/PhoneConversation.java'),str(check)],check=True)
 subprocess.run([str(java/'java.exe'),'-cp',str(root),'app.sakura.mobile.ConversationChecks'],check=True)
