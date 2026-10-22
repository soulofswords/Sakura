package app.sakura.mobile;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.regex.*;
/** Calendar drafts only. Saving and notifications belong to the calendar app. */
final class PhoneCalendarRules {
 static final String MONTHS="january|february|march|april|may|june|july|august|september|october|november|december";
 LocalDate date;ZonedDateTime start,end;String title,stage="";long touched;
 boolean open=false;
 static String eventTitle(String input){
  String title=input.split("\\b(?:so\\s+)?(?:add|put|save|block)\\s+(?:that|it|this)\\b|\\bit\\s+(?:would|will)\\s+be\\b",2)[0]
   .replaceAll("\\b\\d{1,2}(?::\\d{2})?\\s*[ap]m\\b.*","")
   .replaceFirst("^(?:(?:hello|hi|hey|please)[,. ]+|i\\s+have\\s+(?:an?\\s+)?|(?:make|create)\\s+a\\s+schedule\\s+for\\s+(?:my\\s+)?|(?:remind me|set a reminder)\\s+(?:about\\s+)?|(?:there is|there's)\\s+(?:an?\\s+)?)+","")
   .replaceAll("\\b(?:reminder|on|at)\\b"," ").replaceAll("\\s+"," ").replaceAll("^[ ,.-]+|[ ,.-]+$","")
   .replaceFirst("\\s+(?:from|to|until|for my|so)$","").trim();
  return title.isEmpty()?"Reminder":title.substring(0,Math.min(100,title.length()));
 }
 String command(String input,ZonedDateTime now){
  open=false;String text=CommandRules.normalize(input);
  if(System.currentTimeMillis()-touched>600000)stage="";
  if(!stage.isEmpty()&&text.matches("cancel|no|never mind|nevermind")){stage="";return "Cancelled. Nothing was saved.";}
  if(!stage.isEmpty()&&text.matches("yes|yes please|confirm|add it|save it|go ahead")){
   if(!stage.equals("confirm"))return question();stage="";open=true;
   return "Review the filled event in your Calendar app. Choose your Google calendar, set its notification, and tap Save. I cannot confirm saving from Sakura.";
  }
  Matcher match=Pattern.compile("\\b(\\d{1,2})(?:st|nd|rd|th)? ("+MONTHS+")(?: (20\\d{2}))?\\b").matcher(text);
  if(match.find()&&Pattern.compile("\\b(remind(?:er)?|birthday|meeting|appointment|calendar)\\b").matcher(text).find()){
   int month=Arrays.asList(MONTHS.split("\\|")).indexOf(match.group(2))+1;
   try{date=LocalDate.of(match.group(3)==null?now.getYear():Integer.parseInt(match.group(3)),month,Integer.parseInt(match.group(1)));if(match.group(3)==null&&date.isBefore(now.toLocalDate()))date=date.plusYears(1);}catch(DateTimeException e){stage="";return "Please give a valid day, month and year.";}
   title=eventTitle(text.substring(0,match.start())+" "+text.substring(match.end()));
   if(title.isEmpty())title="Reminder";if(title.length()>100)title=title.substring(0,100);
   start=null;end=null;stage="start";
  }else if(stage.isEmpty())return null;
  else if(!text.matches("(?:at |until |ends at )?\\d{1,2}(?::\\d{2})?\\s*[ap]m(?:\\s*(?:to|until|-)\\s*\\d{1,2}(?::\\d{2})?\\s*[ap]m)?"))return null;
  touched=System.currentTimeMillis();Matcher times=Pattern.compile("\\b(\\d{1,2})(?::(\\d{2}))?\\s*([ap]m)\\b").matcher(text);
  List<ZonedDateTime> values=new ArrayList<>();while(times.find()){
   int h=Integer.parseInt(times.group(1)),m=times.group(2)==null?0:Integer.parseInt(times.group(2));
   if(h<1||h>12||m>59)return "Give a valid time, such as 2 pm or 2:30 pm.";
   values.add(date.atTime(h%12+(times.group(3).equals("pm")?12:0),m).atZone(now.getZone()));
  }
  if(!values.isEmpty()){
   if(stage.equals("end"))end=values.get(0);
   else{start=values.get(0);if(values.size()>1)end=values.get(1);else if(title.contains("birthday"))end=start.plusMinutes(15);}
   if(start!=null&&start.isBefore(now)){stage="";return "That time has already passed. Please give a future date and time.";}
   if(end!=null&&!end.isAfter(start)){end=null;stage="end";return "What time does it end, later than the start on that date?";}
   stage=end==null?"end":"confirm";
  }
  return question();
 }
 String question(){
  if(stage.equals("start"))return "What time on "+date+" should I remind you? Please give a clock time; I cannot detect when you wake up.";
  if(stage.equals("end"))return "What time does the meeting or appointment end?";
  return "Prepare "+title+" on "+start.format(DateTimeFormatter.ofPattern("d MMMM uuuu, h:mm a",Locale.ENGLISH))+" to "+end.format(DateTimeFormatter.ofPattern("h:mm a z",Locale.ENGLISH))+" in your Calendar app? Say yes to review and save, or cancel.";
 }
}
