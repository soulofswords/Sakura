package app.sakura.mobile;
import java.net.*;
import java.io.*;
import java.util.*;
import org.json.*;
final class PhoneWeather {
 static final Map<String,JSONObject> cities=new java.util.concurrent.ConcurrentHashMap<>();
 static final Map<String,String> replies=new java.util.concurrent.ConcurrentHashMap<>();
 static final Map<String,Long> times=new java.util.concurrent.ConcurrentHashMap<>();
 static JSONObject get(String url)throws Exception{
  HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setConnectTimeout(5000);c.setReadTimeout(7000);c.setInstanceFollowRedirects(false);c.setRequestProperty("User-Agent","SakuraMobile/0.3.12");
  try{if(c.getResponseCode()!=200)throw new IOException("Weather service returned HTTP "+c.getResponseCode());try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>500000)throw new IOException("Weather response too large.");}return new JSONObject(out.toString("UTF-8"));}}finally{c.disconnect();}
 }
 static String named(String place)throws Exception{
  String key=place.toLowerCase(Locale.ROOT);JSONObject city=cities.get(key);
  if(city==null){
   // Public city-centre coordinate: no device GPS needed for explicit Mumbai requests.
   if(key.equals("mumbai")||key.equals("bombay"))city=new JSONObject().put("name","Mumbai").put("latitude",19.07283).put("longitude",72.88261);
   else{JSONArray found=get("https://geocoding-api.open-meteo.com/v1/search?count=1&language=en&name="+URLEncoder.encode(place,"UTF-8")).optJSONArray("results");if(found==null||found.length()==0)return "I couldn't find a weather location named "+place+". Please give the city name.";city=found.getJSONObject(0);}cities.put(key,city);
  }
  return at(city.getDouble("latitude"),city.getDouble("longitude"),city.getString("name"));
 }
 static String at(double lat,double lon,String area)throws Exception{
  String key=String.format(Locale.ROOT,"%.3f,%.3f",lat,lon);Long saved=times.get(key);if(saved!=null&&System.currentTimeMillis()-saved<300000)return replies.get(key);
  JSONObject data=get("https://api.open-meteo.com/v1/forecast?latitude="+lat+"&longitude="+lon+"&current=temperature_2m,relative_humidity_2m,weather_code&timezone=auto"),c=data.getJSONObject("current");
  String answer="Current weather in "+area+": "+c.getDouble("temperature_2m")+"°C, "+condition(c.getInt("weather_code"))+", humidity "+c.getInt("relative_humidity_2m")+"%. Open-Meteo update: "+c.getString("time")+" ("+data.optString("timezone","local time")+").";
  if(replies.size()>30){replies.clear();times.clear();}replies.put(key,answer);times.put(key,System.currentTimeMillis());return answer;
 }
 static String condition(int c){if(c==0)return "clear skies";if(c<=3)return "partly cloudy or overcast";if(c==45||c==48)return "fog";if(c>=51&&c<=57)return "drizzle";if(c>=61&&c<=67)return "rain";if(c>=71&&c<=77)return "snow";if(c>=80&&c<=82)return "rain showers";if(c==85||c==86)return "snow showers";if(c>=95)return "thunderstorms";return "conditions code "+c;}
}
