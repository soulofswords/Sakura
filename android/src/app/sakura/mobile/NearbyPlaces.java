package app.sakura.mobile;
import android.location.Location;
import java.net.*;
import java.io.*;
import java.util.*;
import org.json.*;

final class NearbyPlaces {
 private static Location cachedAt;private static long cachedTime;private static JSONObject cached;private static String cachedName="";
 static synchronized JSONObject restaurants(Location fix,String area,String searchName)throws Exception{
  if(cachedName.equals(searchName)&&cached!=null&&System.currentTimeMillis()-cachedTime<60000&&cachedAt!=null&&fix.distanceTo(cachedAt)<300)return new JSONObject(cached.toString());
  String query=String.format(Locale.ROOT,"[out:json][timeout:20][maxsize:8388608];nwr[amenity~\"^(restaurant|cafe|fast_food)$\"](around:3000,%.6f,%.6f);out center tags 120;",fix.getLatitude(),fix.getLongitude());
  HttpURLConnection c=(HttpURLConnection)new URL("https://overpass-api.de/api/interpreter").openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(25000);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("User-Agent","SakuraMobile/0.3.5 (https://github.com/soulofswords/Sakura-Downloads)");c.setRequestProperty("Content-Type","application/x-www-form-urlencoded");
  JSONObject data;
  try{
   try(OutputStream out=c.getOutputStream()){out.write(("data="+URLEncoder.encode(query,"UTF-8")).getBytes("UTF-8"));}
   if(c.getResponseCode()!=200)throw new IOException("Nearby map search is unavailable or busy. Please retry later; I haven't verified any restaurants.");
   try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] bytes=new byte[8192];int n;while((n=in.read(bytes))!=-1){out.write(bytes,0,n);if(out.size()>2000000)throw new IOException("Nearby result limit reached. Try again later.");}data=new JSONObject(out.toString("UTF-8"));}
  }finally{c.disconnect();}
  if(data.has("remark"))throw new IOException("The map service could not complete this search. Try again later.");
  JSONArray elements=data.optJSONArray("elements");ArrayList<JSONObject> places=new ArrayList<>();Set<String> seen=new HashSet<>();
  if(elements!=null)for(int i=0;i<elements.length();i++){
   JSONObject item=elements.getJSONObject(i),tags=item.optJSONObject("tags"),point=item.has("lat")?item:item.optJSONObject("center");
   if(tags==null||point==null)continue;String name=tags.optString("name:en",tags.optString("name","")).trim();if(name.isEmpty())continue;
   if(!searchName.isEmpty()&&!name.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]","").contains(searchName.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]","")))continue;
   double lat=point.optDouble("lat",Double.NaN),lon=point.optDouble("lon",Double.NaN);if(!Double.isFinite(lat)||!Double.isFinite(lon))continue;
   double distance=LocationRules.distance(fix.getLatitude(),fix.getLongitude(),lat,lon);if(distance>3000)continue;
   String identity=name.toLowerCase(Locale.ROOT)+Math.round(lat*10000)+":"+Math.round(lon*10000);if(!seen.add(identity))continue;
   String address=(tags.optString("addr:housenumber","")+" "+tags.optString("addr:street","")+" "+tags.optString("addr:suburb","")).trim();
   places.add(new JSONObject().put("name",name.substring(0,Math.min(name.length(),160))).put("address",address.substring(0,Math.min(address.length(),200))).put("distance_m",Math.round(distance)).put("latitude",lat).put("longitude",lon));
  }
  places.sort((a,b)->Long.compare(a.optLong("distance_m"),b.optLong("distance_m")));JSONArray selected=new JSONArray();StringBuilder reply=new StringBuilder();
  if(places.isEmpty())reply.append("I couldn't find "+(searchName.isEmpty()?"named restaurants":searchName)+" in OpenStreetMap within about 3 km of ").append(area).append(". Its listings may be incomplete; that doesn't mean no restaurants exist nearby.");
  else{
   reply.append("Near your current area, ").append(area).append(", I found these mapped food places within about 3 km: ");
   for(int i=0;i<Math.min(5,places.size());i++){JSONObject p=places.get(i);selected.put(p);reply.append(i==0?"":"; ").append(p.getString("name")).append(" (about ").append(p.getLong("distance_m")).append(" m straight-line distance)");}
   reply.append(". Listings are from OpenStreetMap, not live reviews. Opening hours, availability and route distances are unverified.");
  }
  if(fix.getAccuracy()>300)reply.append(" Your phone is providing approximate location, so nearby order and distances are approximate.");
  JSONObject result=new JSONObject().put("reply",reply.toString()).put("places",selected).put("source","© OpenStreetMap contributors · Overpass API").put("location_area",area);
  result.put("maps_search",new JSONObject().put("latitude",fix.getLatitude()).put("longitude",fix.getLongitude()).put("query",searchName.isEmpty()?"restaurants":searchName));
  cachedName=searchName;cached=result;cachedAt=new Location(fix);cachedTime=System.currentTimeMillis();return new JSONObject(result.toString());
 }
}
