package app.sakura.mobile;
import android.Manifest;
import android.content.pm.PackageManager;
import android.location.*;
import android.os.*;
import android.app.AlertDialog;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.json.*;

final class PhoneLocation {
 final MainActivity activity;volatile boolean awaitingPermission=false;private CountDownLatch permission;
 volatile Location last;volatile String area="";
 volatile Runnable cancelFix;
 void stop(){Runnable stop=cancelFix;if(stop!=null)activity.runOnUiThread(stop);}
 PhoneLocation(MainActivity activity){this.activity=activity;}
 boolean granted(){return activity.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED||activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED;}
 String preference(){return activity.getSharedPreferences("paired-pcs",0).getString("location-mode","ask");}
 void setting(String value){activity.getSharedPreferences("paired-pcs",0).edit().putString("location-mode",value).apply();if(value.equals("off")){last=null;area="";}}
 boolean enabled(){return preference().equals("on")&&granted();}
 synchronized void permissions()throws Exception{
  if(!activity.phoneForeground)throw new IOException("Open Sakura to use current location.");
  permission=new CountDownLatch(1);awaitingPermission=true;
  activity.runOnUiThread(()->new AlertDialog.Builder(activity).setTitle("Use your current location?").setMessage("Sakura uses location while open for your current area, weather and nearby restaurants. Your area may go to your selected AI provider. Android services resolve the area; coordinates go to OpenStreetMap/Overpass for places and Open-Meteo for weather. No location history is saved. You can turn this off in Local settings.").setPositiveButton("Enable",(d,w)->{if(granted()){setting("on");permissionsResult();}else activity.requestPermissions(new String[]{Manifest.permission.ACCESS_COARSE_LOCATION,Manifest.permission.ACCESS_FINE_LOCATION},5);}).setNegativeButton("Not now",(d,w)->{setting("off");permissionsResult();}).setOnCancelListener(d->{setting("off");permissionsResult();}).show());
  try{if(!permission.await(90,TimeUnit.SECONDS))throw new IOException("Location permission request timed out. Try again in Local settings.");}finally{awaitingPermission=false;}
  if(!enabled())throw new IOException("Location is off or permission was denied. Enable Current location in Local settings, or tell me your city.");
 }
 void permissionsResult(){if(granted()&&!preference().equals("off"))setting("on");else setting("off");awaitingPermission=false;if(permission!=null)permission.countDown();}
 Location current(boolean explicit)throws Exception{
  if(preference().equals("off"))throw new IOException("Current location is off. Enable it in Local settings or tell me the city you want.");
  if(!enabled()){if(explicit)permissions();else return null;}
  if(!activity.phoneForeground)throw new IOException("Open Sakura to refresh location.");
  LocationManager manager=(LocationManager)activity.getSystemService(android.content.Context.LOCATION_SERVICE);
  if(manager==null||!manager.isLocationEnabled())throw new IOException("Turn on Location/GPS in Android settings, then try again.");
  CountDownLatch ready=new CountDownLatch(1);AtomicReference<Location> found=new AtomicReference<>();
  LocationListener listener=new LocationListener(){public void onLocationChanged(Location value){if(valid(value)){found.set(value);ready.countDown();}}public void onProviderEnabled(String p){}public void onProviderDisabled(String p){}public void onStatusChanged(String p,int s,Bundle extras){}};
  Runnable cancel=()->{manager.removeUpdates(listener);ready.countDown();};cancelFix=cancel;
  activity.runOnUiThread(()->{
   try{
    for(String provider:new String[]{LocationManager.NETWORK_PROVIDER,LocationManager.GPS_PROVIDER}){
     if(!manager.isProviderEnabled(provider))continue;
     Location cached=manager.getLastKnownLocation(provider);if(valid(cached)){Location prior=found.get();if(prior==null||cached.getElapsedRealtimeNanos()>prior.getElapsedRealtimeNanos())found.set(cached);}
     try{manager.requestLocationUpdates(provider,1000,0,listener,Looper.getMainLooper());}catch(SecurityException ignored){}
    }
    if(found.get()!=null)ready.countDown();
   }catch(Exception ignored){ready.countDown();}
  });
  try{ready.await(18,TimeUnit.SECONDS);}finally{activity.runOnUiThread(()->manager.removeUpdates(listener));if(cancelFix==cancel)cancelFix=null;}
  Location fix=found.get();if(!valid(fix))throw new IOException("No fresh location fix yet. Move near a window, check GPS and retry. I won't reuse your old city.");
  if(!enabled()||!activity.phoneForeground)throw new IOException("Location access stopped. Reopen Sakura and try again.");
  last=new Location(fix);area=area(fix);return fix;
 }
 boolean valid(Location value){return value!=null&&LocationRules.fresh(SystemClock.elapsedRealtime(),value.getElapsedRealtimeNanos()/1000000,value.getAccuracy());}
 String area(Location fix){
  try{if(Geocoder.isPresent()){List<Address> matches=new Geocoder(activity,Locale.ENGLISH).getFromLocation(fix.getLatitude(),fix.getLongitude(),1);if(matches!=null&&!matches.isEmpty()){Address a=matches.get(0);LinkedHashSet<String> parts=new LinkedHashSet<>();for(String s:new String[]{a.getSubLocality(),a.getLocality(),a.getAdminArea(),a.getCountryName()})if(s!=null&&!s.isEmpty())parts.add(s);if(!parts.isEmpty())return String.join(", ",parts);}}}catch(Exception ignored){}
  return String.format(Locale.ROOT,"area near %.2f, %.2f (city lookup unavailable)",fix.getLatitude(),fix.getLongitude());
 }
 JSONObject state()throws Exception{return new JSONObject().put("enabled",enabled()).put("permission",granted()).put("area",enabled()&&valid(last)?area:"").put("fresh",enabled()&&valid(last));}
 String context(Location fix){return "Current phone location was refreshed for this request: "+area+". Fix age "+Math.max(0,(SystemClock.elapsedRealtime()-fix.getElapsedRealtimeNanos()/1000000)/1000)+" seconds, accuracy about "+Math.round(fix.getAccuracy())+" metres. This current area overrides older conversation locations. A past mention of Mumbai is not proof the user is there now. Do not invent nearby businesses or claim to track travel history. No exact street address is provided.";}
}
