package app.sakura.mobile;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.provider.AlarmClock;
import java.io.*;
import java.net.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.regex.*;
import org.json.*;

final class PhoneAssistant {
 final Activity activity;
 PhoneAssistant(Activity activity){this.activity=activity;}
 static byte[] http(String url,String method,String key,String provider,JSONObject body,int limit)throws Exception{
  HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(12000);c.setReadTimeout(90000);c.setRequestMethod(method);
  c.setRequestProperty("Content-Type","application/json");
  if(!key.isEmpty())c.setRequestProperty(provider.equals("gemini")?"x-goog-api-key":"Authorization",provider.equals("gemini")?key:"Bearer "+key);
  try{
   if(body!=null){c.setDoOutput(true);try(OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes("UTF-8"));}}
   int code=c.getResponseCode();if(code>=400){
    String raw="",errorCode="",errorType="",detail="";
    try(InputStream in=c.getErrorStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
     if(in!=null){byte[] buffer=new byte[2048];int n;while(out.size()<16384&&(n=in.read(buffer,0,Math.min(buffer.length,16384-out.size())))!=-1)out.write(buffer,0,n);raw=out.toString("UTF-8");}
    }
    try{JSONObject error=new JSONObject(raw).optJSONObject("error");if(error!=null){errorCode=error.optString("code","");errorType=error.optString("type",error.optString("status",""));detail=error.optString("message","");}}catch(Exception ignored){}
    throw new IOException(ProviderErrors.describe(provider,code,errorCode,errorType,detail,c.getHeaderField("Retry-After"),key));
   }
   try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
    byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){out.write(buffer,0,n);if(out.size()>limit)throw new IOException("Response exceeds size limit");}return out.toByteArray();
   }
  }finally{c.disconnect();}
 }
 static JSONObject json(String url,String method,String key,String provider,JSONObject body)throws Exception{return new JSONObject(new String(http(url,method,key,provider,body,2000000),"UTF-8"));}
 static JSONArray models(String provider,String key)throws Exception{
  JSONArray result=new JSONArray();String page="";
  for(int p=0;p<5;p++){
   JSONObject data=json(provider.equals("gemini")?"https://generativelanguage.googleapis.com/v1beta/models?pageSize=100"+(page.isEmpty()?"":"&pageToken="+URLEncoder.encode(page,"UTF-8")):"https://api.openai.com/v1/models","GET",key,provider,null);
   JSONArray entries=data.optJSONArray(provider.equals("gemini")?"models":"data");if(entries==null)throw new IOException("Provider returned no model catalog.");
   for(int i=0;i<entries.length();i++){
    JSONObject entry=entries.getJSONObject(i);String id=entry.optString(provider.equals("gemini")?"name":"id").replaceFirst("^models/","");
    if(!id.matches("[A-Za-z0-9_.-]{1,100}"))continue;
    if(provider.equals("gemini")){JSONArray methods=entry.optJSONArray("supportedGenerationMethods");boolean chat=false;if(methods!=null)for(int j=0;j<methods.length();j++)if(methods.optString(j).equals("generateContent"))chat=true;if(!chat||id.contains("tts")||id.contains("image")||!id.startsWith("gemini"))continue;}
    else if(!(id.startsWith("gpt-")||id.matches("o[0-9].*"))||id.matches(".*(?:audio|realtime|transcribe|image|tts|search|instruct|codex|pro).*")||id.contains("chatgpt"))continue;
    result.put(id);
   }
   page=data.optString("nextPageToken","");if(!provider.equals("gemini")||page.isEmpty())break;
  }
  return result;
 }
 JSONObject check(String provider,String key,String model)throws Exception{
  JSONObject result;
  if(provider.equals("gemini"))result=json("https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent","POST",key,provider,new JSONObject().put("contents",new JSONArray().put(new JSONObject().put("role","user").put("parts",new JSONArray().put(new JSONObject().put("text","Reply with OK."))))).put("generationConfig",new JSONObject().put("maxOutputTokens",64)));
  else result=json("https://api.openai.com/v1/chat/completions","POST",key,provider,new JSONObject().put("model",model).put("messages",new JSONArray().put(new JSONObject().put("role","user").put("content","Reply with OK."))).put("max_completion_tokens",32));
  if(!(provider.equals("gemini")?result.has("candidates"):result.has("choices")))throw new IOException("The provider did not return a chat response. Check the selected model.");
  return new JSONObject().put("ok",true).put("model",model).put("message","API test Passed · "+model+" accepted a generation request. This does not test voice quota.");
 }
 static String clean(String text){return text.replaceAll("(?i)\\*{1,2}(?:leans?|winks?|smiles?|adjusts?|giggles?)[^*]{0,180}\\*{1,2}","").replaceAll("(?i)\\((?:leans?|winks?|smiles?|adjusts?)[^)]{0,160}\\)","").replace("*","").replace("`","").trim();}
 JSONObject reply(JSONArray history,String provider,String key,String model,String address)throws Exception{
  if(history.length()==0||history.length()>40)throw new IOException("Send a message first.");
  JSONObject last=history.getJSONObject(history.length()-1);if(!last.optString("role").equals("user"))throw new IOException("Last message must be yours.");
  String text=last.getString("content");if(text.length()>10000)throw new IOException("Message too long.");
  String action=command(text);if(action!=null)return new JSONObject().put("reply",action);
  String title=address.equals("maam")?"Ma’am":address.equals("none")?"":"Sir";
  String system="You are Sakura, a warm practical phone AI assistant. Answer the actual question naturally in 1–3 concise complete sentences. Never repeat phrases, introduce yourself every turn, narrate stage actions or use asterisks. Use "+(title.isEmpty()?"no honorific":title+" occasionally")+", never Master. Current phone time: "+new SimpleDateFormat("EEEE yyyy-MM-dd HH:mm z",Locale.ENGLISH).format(new Date())+". Never claim you opened an app or fetched live facts unless the app confirmed that action. You cannot see the phone screen or camera. Local means phone rendering with a cloud API, not an offline AI model. Available dances: groove, step, wave, twist, disco, march. Only explicit user dance requests may trigger these.";
  JSONObject result;
  if(provider.equals("gemini")){
   JSONArray contents=new JSONArray();for(int i=0;i<history.length();i++){JSONObject m=history.getJSONObject(i);String role=m.optString("role");if(!role.equals("user")&&!role.equals("assistant"))continue;contents.put(new JSONObject().put("role",role.equals("assistant")?"model":"user").put("parts",new JSONArray().put(new JSONObject().put("text",m.getString("content")))));}
   result=json("https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent","POST",key,provider,new JSONObject().put("systemInstruction",new JSONObject().put("parts",new JSONArray().put(new JSONObject().put("text",system)))).put("contents",contents).put("generationConfig",new JSONObject().put("maxOutputTokens",768).put("temperature",.5)));
   JSONArray parts=result.getJSONArray("candidates").getJSONObject(0).getJSONObject("content").getJSONArray("parts");StringBuilder answer=new StringBuilder();for(int i=0;i<parts.length();i++)if(!parts.getJSONObject(i).optBoolean("thought"))answer.append(parts.getJSONObject(i).optString("text"));
   return new JSONObject().put("reply",clean(answer.toString()));
  }
  JSONArray messages=new JSONArray().put(new JSONObject().put("role","system").put("content",system));for(int i=0;i<history.length();i++){JSONObject m=history.getJSONObject(i);if(m.optString("role").matches("user|assistant"))messages.put(m);}
  result=json("https://api.openai.com/v1/chat/completions","POST",key,provider,new JSONObject().put("model",model).put("messages",messages).put("max_completion_tokens",512));
  return new JSONObject().put("reply",clean(result.getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content")));
 }
 String command(String input)throws Exception{
  String text=input.toLowerCase(Locale.ROOT).trim().replaceAll("[?!.,]+$","");
  Matcher call=Pattern.compile("(?:(?:can|could|would) you |please )?(?:call|phone) (.{1,100})").matcher(text);
  if(call.matches()){
   ((MainActivity)activity).requestCall(call.group(1));
   return "Check the call confirmation on your phone. I will stay muted during the call.";
  }
  if(text.matches("(?:what(?:'s| is) (?:the )?(?:current )?time(?: is it)?|tell me (?:the )?time|time now)"))return "It's "+new SimpleDateFormat("h:mm a",Locale.getDefault()).format(new Date())+".";
  if(text.matches("(?:what(?:'s| is) (?:the |today's )?date|what day is it|tell me (?:the )?date)"))return new SimpleDateFormat("EEEE, d MMMM yyyy",Locale.getDefault()).format(new Date());
  Matcher open=Pattern.compile("(?:(?:can|could) you |please )?(?:open|launch|start) (.{1,80})").matcher(text);
  if(open.matches()){
   String name=open.group(1);List<ResolveInfo> apps=activity.getPackageManager().queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),0);
   for(ResolveInfo info:apps){String label=info.loadLabel(activity.getPackageManager()).toString();if(label.equalsIgnoreCase(name)||info.activityInfo.packageName.equalsIgnoreCase(name)){
    Intent launch=activity.getPackageManager().getLaunchIntentForPackage(info.activityInfo.packageName);if(launch!=null){activity.runOnUiThread(()->{try{activity.startActivity(launch);}catch(Exception ignored){}});return "Opening "+label+".";}
   }}return "I couldn't find "+name+" installed on this phone.";
  }
  Matcher timer=Pattern.compile("(?:(?:set|make|start) (?:a )?)(\\d{1,4})[ -]*(second|minute|hour)s?(?: timer)?").matcher(text);
  if(timer.matches()){int seconds=Integer.parseInt(timer.group(1))*(timer.group(2).equals("hour")?3600:timer.group(2).equals("minute")?60:1);if(seconds<1||seconds>86400)return "Choose a timer between one second and 24 hours.";Intent intent=new Intent(AlarmClock.ACTION_SET_TIMER).putExtra(AlarmClock.EXTRA_LENGTH,seconds).putExtra(AlarmClock.EXTRA_MESSAGE,"Sakura timer");return launchClock(intent,"Opening your clock app to set the timer.");}
  Matcher alarm=Pattern.compile("(?:set|make) (?:an? )?alarm (?:for |at )?(\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)?").matcher(text);
  if(alarm.matches()){int hour=Integer.parseInt(alarm.group(1)),minute=alarm.group(2)==null?0:Integer.parseInt(alarm.group(2));String period=alarm.group(3);if(minute>59||hour>23||(period!=null&&(hour<1||hour>12)))return "Please give a valid alarm time.";if(period!=null)hour=hour%12+(period.equals("pm")?12:0);return launchClock(new Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR,hour).putExtra(AlarmClock.EXTRA_MINUTES,minute).putExtra(AlarmClock.EXTRA_MESSAGE,"Sakura alarm"),"Opening your clock app to set the alarm.");}
  Matcher weather=Pattern.compile(".*\\bweather (?:in|for|of) (.{1,80})").matcher(text);
  if(weather.matches()){
   String place=weather.group(1);JSONObject geo=json("https://geocoding-api.open-meteo.com/v1/search?count=1&language=en&name="+URLEncoder.encode(place,"UTF-8"),"GET","","",null);JSONArray found=geo.optJSONArray("results");if(found==null||found.length()==0)return "I couldn't find that location. Which city?";JSONObject city=found.getJSONObject(0),data=json("https://api.open-meteo.com/v1/forecast?latitude="+city.getDouble("latitude")+"&longitude="+city.getDouble("longitude")+"&current=temperature_2m,relative_humidity_2m&timezone=auto","GET","","",null),current=data.getJSONObject("current");return "Current weather in "+city.getString("name")+": "+current.getDouble("temperature_2m")+"°C, humidity "+current.getInt("relative_humidity_2m")+"%. Source: Open-Meteo, "+current.getString("time")+".";
  }
  if(text.matches(".*\\b(?:latest news|news headlines|today's news|news today)\\b.*")){
   String rss=new String(http("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en","GET","","",null,1000000),"UTF-8");org.xmlpull.v1.XmlPullParser parser=android.util.Xml.newPullParser();parser.setInput(new StringReader(rss));StringBuilder out=new StringBuilder("Recent headlines from Google News: ");boolean item=false;int count=0;for(int event=parser.getEventType();event!=org.xmlpull.v1.XmlPullParser.END_DOCUMENT&&count<3;event=parser.next()){if(event==org.xmlpull.v1.XmlPullParser.START_TAG&&parser.getName().equals("item"))item=true;if(item&&event==org.xmlpull.v1.XmlPullParser.START_TAG&&parser.getName().equals("title")){out.append(parser.nextText()).append(". ");count++;item=false;}}return count>0?out.toString():"News headlines are unavailable right now.";
  }
  return null;
 }
 String launchClock(Intent intent,String message){if(intent.resolveActivity(activity.getPackageManager())==null)return "No compatible clock app was found.";activity.runOnUiThread(()->activity.startActivity(intent));return message;}
 String speech(String text,String provider,String key,String voice,File folder)throws Exception{
  text=clean(text);if(text.isEmpty()||text.length()>4000)throw new IOException("Speech text is empty or too long.");byte[] audio;
  if(provider.equals("gemini")){
   JSONObject result=json("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts:generateContent","POST",key,provider,new JSONObject().put("contents",new JSONArray().put(new JSONObject().put("role","user").put("parts",new JSONArray().put(new JSONObject().put("text",text))))).put("generationConfig",new JSONObject().put("responseModalities",new JSONArray().put("AUDIO")).put("speechConfig",new JSONObject().put("voiceConfig",new JSONObject().put("voice",voice.equals("male")?"Charon":"Kore")))));
   JSONObject inline=result.getJSONArray("candidates").getJSONObject(0).getJSONObject("content").getJSONArray("parts").getJSONObject(0).getJSONObject("inlineData");audio=android.util.Base64.decode(inline.getString("data"),android.util.Base64.DEFAULT);
   if(audio.length<4||!new String(audio,0,4,"US-ASCII").equals("RIFF"))throw new IOException("Provider returned unsupported audio; a WAV response is required.");
  }else audio=http("https://api.openai.com/v1/audio/speech","POST",key,provider,new JSONObject().put("model","tts-1").put("voice",voice.equals("male")?"onyx":"nova").put("input",text).put("response_format","wav"),20000000);
  folder.mkdirs();File[] old=folder.listFiles();if(old!=null)for(File file:old)if(file.lastModified()<System.currentTimeMillis()-3600000)file.delete();
  File file=new File(folder,UUID.randomUUID()+".wav");try(FileOutputStream out=new FileOutputStream(file)){out.write(audio);}return "/local-audio/"+file.getName();
 }
}
