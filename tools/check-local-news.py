"""Exercise Android news queries without GPS, a device or API keys."""
from pathlib import Path
import subprocess
import tempfile
BASE=Path(__file__).resolve().parents[1]
java=next((BASE/'tools/android-cache/jdk').rglob('javac.exe')).parent
source='''package app.sakura.mobile;
public class NewsChecks {
 public static void main(String[] args){
  String[][] cases={{"local news","Maharashtra","Maharashtra India"},{"news near me","Mumbai","Mumbai India"},{"latest news","Maharashtra","Maharashtra India"},{"news in Delhi","Mumbai","delhi"},{"news for Mumbai","Delhi","mumbai"},{"India news","Mumbai","india"},{"technology news","Mumbai","technology"},{"news","",""}};
  for(String[] c:cases)if(!c[2].equals(NewsRules.query(c[0],c[1])))throw new AssertionError(c[0]);
  if(NewsRules.query("local news","")!=null)throw new AssertionError("No guessed location");
  long clock=java.time.Instant.parse("2026-10-21T20:45:00Z").toEpochMilli();
  if(!NewsRules.bulletinTime(clock).equals("22 October 2026, 02:15 AM IST. "))throw new AssertionError("Date rollover to IST");
  String chat="21 October 2026, 07:06 AM IST. Recent headlines from Google News: Mumbai train - Publisher.\\nAnother headline - Another Publisher.\\n";
  String spoken=NewsRules.spoken(chat);
  if(!spoken.equals("21 October 2026, 07:06 AM IST. Here are the headlines: Mumbai train. Another headline."))throw new AssertionError(spoken);
  if(!NewsRules.spoken("The meeting is on 21 October.").equals("The meeting is on 21 October."))throw new AssertionError("Regular dialogue unchanged");
  System.out.println("PASS: Android India/local news, saved area, explicit override and missing location");
 }
}'''
with tempfile.TemporaryDirectory(prefix='news-rules-',dir=BASE/'audit-results') as directory:
    folder=Path(directory);file=folder/'NewsChecks.java';file.write_text(source,encoding='utf-8')
    files=[BASE/'android/src/app/sakura/mobile'/name for name in ('CommandRules.java','NewsRules.java')]
    subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(folder),*map(str,files),str(file)],check=True)
    subprocess.run([str(java/'java.exe'),'-cp',str(folder),'app.sakura.mobile.NewsChecks'],check=True)
