package app.sakura.mobile;
import java.util.*;
import java.util.regex.*;
final class PhoneConversation {
 static final String RULES=" You are an AI represented by a digital avatar, without independent friends, possessions, employment or offscreen adventures. Never invent personal lore or say we discussed or you told me unless an earlier USER message supports it. Earlier assistant statements are unverified. Ask a brief clarification for unclear recognition rather than inventing a topic. Do not begin every reply with Oh, I see or praise the question instead of answering. Understand btw as by the way. Acknowledge affection naturally without inventing promises. If an avatar detail or body measurement cannot be determined from evidence, say so; never guess cup sizes. Hindi and Romanized Hindi input should receive ordinary, grammatical Hindi, not translated instructions, irrelevant filler or gender assumptions about the user. Never read emojis or stage actions as dialogue. Never invent exact specifications, numbers, citations or sources to fill missing knowledge. For current prices, product specifications or availability, use verified evidence or say you cannot verify it. Never claim to search or complete actions without an actual tool result. Hardware usage is momentary load, not a specification or proof of performance.";
 static boolean garbled(String answer){return Pattern.compile("सरल बातचीत के लिए.*सहमति|मुझे प्रश्न या विचार देखने|सभी देखने के लिए उम्मीद|गुणवत्ता के खेल|मेरा [ज़ज]िक्र है").matcher(answer).find();}
 static Set<String> words(String text){Set<String> result=new HashSet<>();for(String word:text.toLowerCase(Locale.ROOT).split("[^\\p{L}\\p{N}]+"))if(!word.isEmpty())result.add(word);return result;}
 static boolean repeated(String answer,String old){
  Set<String> a=words(answer),b=words(old);if(a.size()<10||b.size()<10)return false;
  Set<String> intersection=new HashSet<>(a);intersection.retainAll(b);Set<String> union=new HashSet<>(a);union.addAll(b);
  return !union.isEmpty()&&(double)intersection.size()/union.size()>=.84;
 }
 static boolean bad(String answer,String question,List<String> prior){
  if(answer.trim().isEmpty()||garbled(answer))return true;
  if(answer.matches("(?is).*(?:great question|can definitely help|just here to chat).{0,220}(?:what kind of things|what do you think|talk about something|something more meaningful).*"))return true;
  if(!question.matches("(?is).*\\b(?:repeat|say (?:that|it) again|same words|quote)\\b.*"))for(String old:prior)if(repeated(answer,old))return true;
  String[] sentences=answer.toLowerCase(Locale.ROOT).split("[.!?।]+\\s*");Map<String,Integer> counts=new HashMap<>();
  for(String sentence:sentences){String t=sentence.trim();if(t.length()<15)continue;int count=counts.containsKey(t)?counts.get(t)+1:1;counts.put(t,count);if(count>=3)return true;}
  return false;
 }
 static boolean unsupportedLore(String answer,String question){
  if(question.matches("(?is).*\\b(?:story|fiction|roleplay|pretend)\\b.*")||question.contains("कहानी"))return false;
  if(answer.matches("(?is).*\\b(?:made (?:that|it|this) up|invented (?:that|it|this)|fictional character)\\b.*"))return false;
  return answer.matches("(?s).*\\b[Mm]y (?:friend|buddy|colleague|pet) [A-Z][a-z]+.*")||answer.matches("(?is).*\\b(?:my secret weapon|my digital confidant|snack-slinger|I have been in charge|I was born|I grew up)\\b.*");
 }
 static String common(String question){
  String q=question.toLowerCase(Locale.ROOT).replaceAll("[?.!।,]","").trim().replaceAll("\\s+"," ");
  if(q.matches("(?:kya )?(?:a+p+ko|tumhe|tumko) hindi (?:ati|aati) (?:hai|h|he)|(?:क्या )?(?:आपको|आप को) (?:हिंदी|हिन्दी) आती है"))return "हाँ, हम हिंदी में बात कर सकते हैं।";
  if(q.matches("(?:a+p+|tum) (?:kaise|kese|kaisi|kesi) (?:ho|hain|hai)|(?:आप|तुम) (?:कैसे|कैसी) (?:हो|हैं|है)"))return "सब बढ़िया! आप कैसे हैं?";
  if(q.matches("(?:a+p+|tum) ladk[ae] ho (?:kya|ya) ladki|(?:आप|तुम) लड़क[ाे] हो (?:क्या|या) लड़की"))return "मैं एक एआई सहायक हूँ। मेरा दिखना आपके चुने हुए अवतार पर निर्भर है।";
  return null;
 }
 static String spoken(String text){return text.replaceAll("[\\x{1F000}-\\x{1FAFF}\\x{2600}-\\x{27BF}\\x{FE0E}\\x{FE0F}\\x{200D}\\x{20E3}]","").trim();}
}
