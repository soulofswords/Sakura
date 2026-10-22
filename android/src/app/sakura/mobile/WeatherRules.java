package app.sakura.mobile;
import java.util.Locale;
import java.util.regex.*;
final class WeatherRules {
 static boolean weather(String text){return text.toLowerCase(Locale.ROOT).matches("(?s).*(?:\\bweather\\b|\\btemperature\\b|मौसम|mausam).*");}
 static String city(String text){
  String t=text.trim().replaceAll("[?!.,]+$","");
  Matcher m=Pattern.compile("(?i)(?:weather|temperature)(?:\\s+(?:right now|now|currently|today))?\\s+(?:in|for|of|at)\\s+(.{2,80})").matcher(t);
  String city="";if(m.find())city=m.group(1);
  else{m=Pattern.compile("(?i)(?:weather|temperature)\\s+(?!here\\b|now\\b|today\\b|tomorrow\\b)([\\p{L}][\\p{L} .'-]{1,60})$").matcher(t);if(m.find())city=m.group(1);else{m=Pattern.compile("(?i)^([\\p{L}][\\p{L} .'-]{1,60})(?:'s weather| (?:ka mausam|का मौसम))").matcher(t);if(m.find())city=m.group(1);}}
  return city.replaceAll("(?i)(?:\\s+(?:right now|now|currently|today|please|this morning|this evening))+$","").trim();
 }
 static boolean current(String text){return weather(text)&&!text.toLowerCase(Locale.ROOT).matches("(?s).*(?:tomorrow|yesterday|next week|forecast|20[0-9]{2}|कल|अगले).*");}
}
