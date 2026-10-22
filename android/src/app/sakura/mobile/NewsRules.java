package app.sakura.mobile;
import java.util.regex.*;
final class NewsRules {
 static String spoken(String text){
  if(!text.contains("Recent headlines from Google News:"))return text;
  text=text.replace("Recent headlines from Google News:","Here are the headlines:");
  // Each RSS headline is a separate line; only its final publisher suffix is removed.
  StringBuilder out=new StringBuilder();
  for(String line:text.split("\\n")){
   int publisher=line.lastIndexOf(" - ");
   if(publisher>=0)line=line.substring(0,publisher).replaceFirst("[. ]+$","")+".";
   out.append(line.trim()).append(' ');
  }
  return out.toString().trim();
 }
 static String bulletinTime(long now){
  java.text.SimpleDateFormat format=new java.text.SimpleDateFormat("dd MMMM yyyy, hh:mm a",java.util.Locale.ENGLISH);
  format.setTimeZone(java.util.TimeZone.getTimeZone("Asia/Kolkata"));
  return format.format(new java.util.Date(now))+" IST. ";
 }
 static String query(String request,String area){
  String text=CommandRules.normalize(request).replaceFirst("^(?:(?:tell|show|give) me |get |read )","");
  Matcher explicit=Pattern.compile("\\b(?:news|headlines)\\s+(?:about|on|in|for|of|from)\\s+(.+)").matcher(text);
  String query=explicit.find()?explicit.group(1).trim():text.replaceAll("\\b(?:the|latest|current|today|today's|any|some|news|headlines|please|now)\\b","").trim();
  String saved=area==null?"":area.trim();
  if(query.matches("(?:local|my city|my state|near me|around me|here|in my area|for my area|my area)"))return saved.isEmpty()?null:saved+" India";
  if(query.isEmpty()&&!saved.isEmpty())return saved+" India";
  return query.length()>180?query.substring(0,180):query;
 }
}
