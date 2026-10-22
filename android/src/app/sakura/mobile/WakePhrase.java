package app.sakura.mobile;
import java.util.Locale;

final class WakePhrase {
 static String normalize(String text){return text.toLowerCase(Locale.ROOT).replaceAll("[^a-z ]"," ").trim().replaceAll(" +"," ");}
 static String validate(String text){String p=normalize(text);if(!text.matches("[A-Za-z '-]{3,70}")||p.split(" ").length<2||p.split(" ").length>6)throw new IllegalArgumentException("Use a wake phrase of 2–6 English words, such as Hey Sakura.");return p;}
 static boolean matches(String heard,String phrase){return normalize(heard).equals(phrase);}
 static boolean confident(String heard,String phrase,double[] confidence,double duration){if(!matches(heard,phrase)||confidence.length!=phrase.split(" ").length||duration<.35||duration>4.5)return false;double total=0;for(double c:confidence){if(!Double.isFinite(c)||c<.85)return false;total+=c;}return total/confidence.length>=.92;}
 static boolean meaningfulCommand(String text){String t=normalize(text);return !t.isEmpty()&&!t.matches("(?:(?:huh|uh|um|hm|hmm|ah|oh|eh|er|erm|ha|hmmh|mm) ?)+");}
 static String trimCommand(String heard,String phrase){String t=normalize(heard);return t.equals(phrase)?"":t.startsWith(phrase+" ")?t.substring(phrase.length()+1):t;}
}
