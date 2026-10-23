package app.sakura.mobile;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.*;
import android.content.pm.PackageManager;
import android.content.Intent;
import android.speech.RecognizerIntent;
import android.Manifest;
import java.io.*;
import java.net.*;
import org.json.*;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.security.KeyStore;

public class MainActivity extends Activity {
 private boolean localAvailable=true;
 private CallController calls;
 private static java.lang.ref.WeakReference<MainActivity> current=new java.lang.ref.WeakReference<>(null);
 private volatile boolean assistantReady;private String wakePermissionId;private boolean wakePermissionPending;
 static boolean deliverWakeCommand(String text){MainActivity a=current.get();if(a==null||!a.phoneForeground||!a.assistantReady||WakeService.uiBusy)return false;java.util.concurrent.CountDownLatch ready=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicBoolean accepted=new java.util.concurrent.atomic.AtomicBoolean();a.runOnUiThread(()->{if(!a.phoneForeground||!a.assistantReady){ready.countDown();return;}a.web.evaluateJavascript("window.sakuraWakeCommand?.("+JSONObject.quote(text)+")==true",result->{accepted.set("true".equals(result));ready.countDown();});});try{ready.await(2,java.util.concurrent.TimeUnit.SECONDS);}catch(InterruptedException ignored){Thread.currentThread().interrupt();}return accepted.get();}
 private String wakeState(){try{android.content.SharedPreferences p=getSharedPreferences("paired-pcs",0);return new JSONObject().put("download_active",WakeAssets.downloading).put("download_status",WakeAssets.downloadStatus).put("download_bytes",new File(getCacheDir(),"wake-model.download").length()).put("installed",WakeAssets.ready(this)).put("enabled",WakeService.live!=null&&!WakeService.live.stopped).put("phrase",p.getString("wake-phrase","hey sakura")).put("status",p.getString("wake-status","Wake phrase off")).toString();}catch(Exception error){return "{}";}}
 private void startWake(String id){try{if(!phoneForeground)throw new Exception("Open Sakura before enabling the wake microphone.");if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)throw new Exception("Microphone permission is required.");if(!getSystemService(android.app.NotificationManager.class).areNotificationsEnabled())throw new Exception("Enable Sakura notifications in Android settings so the wake listener has a visible Stop control.");microphone.stop();WakeService.manual=false;startForegroundService(new Intent(this,WakeService.class).setAction("START"));web.postDelayed(()->new Bridge().complete(id,wakeState()),300);}catch(Exception error){try{new Bridge().complete(id,new JSONObject().put("error",error.getMessage()).toString());}catch(Exception ignored){}}}

 private PhoneMicrophone microphone;private boolean modelFullscreen;private int microphoneGeneration;private boolean dictationPending;
 void microphoneEvent(boolean on,String message,String text){if(!on&&!dictationPending)WakeService.pauseManual(false);if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraMicrophone?.("+on+","+JSONObject.quote(message)+","+(text==null?"null":JSONObject.quote(text))+")",null));}
 private void fullscreen(boolean enabled){modelFullscreen=enabled;android.view.View decor=getWindow().getDecorView();if(android.os.Build.VERSION.SDK_INT>=30){getWindow().setDecorFitsSystemWindows(!enabled);android.view.WindowInsetsController controller=decor.getWindowInsetsController();if(controller!=null){controller.setSystemBarsBehavior(android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);if(enabled)controller.hide(android.view.WindowInsets.Type.systemBars());else controller.show(android.view.WindowInsets.Type.systemBars());}}else decor.setSystemUiVisibility(enabled?android.view.View.SYSTEM_UI_FLAG_FULLSCREEN|android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|android.view.View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE:android.view.View.SYSTEM_UI_FLAG_VISIBLE);}
 @Override public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(focus&&modelFullscreen)fullscreen(true);}
 @Override public void onBackPressed(){if(modelFullscreen&&web!=null)web.evaluateJavascript("window.sakuraExitModelFullscreen?.()",null);else super.onBackPressed();}
 PhoneLocation locations;volatile boolean phoneForeground=false;
 void callState(boolean active){if(active&&microphone!=null)runOnUiThread(()->{microphone.stop();microphone.state(false,"Call in progress · microphone off");});if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraCallState?.("+active+")",null));}
 void phoneNotice(String text){if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraPhoneNotice?.("+JSONObject.quote(text)+")",null));}
 void requestCall(String person){if(localAvailable&&calls!=null)calls.request(person);}
 private WebView web; private String base="",token=""; private PermissionRequest cameraRequest;
 @Override public void onCreate(Bundle state){
  super.onCreate(state);getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);current=new java.lang.ref.WeakReference<>(this); web=new WebView(this);setContentView(web);if(localAvailable){calls=new CallController(this);locations=new PhoneLocation(this);microphone=new PhoneMicrophone(this);}
  web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);
  web.getSettings().setMediaPlaybackRequiresUserGesture(false);
  web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);
  web.addJavascriptInterface(new Bridge(),"Sakura");
  web.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !"appassets.androidplatform.net".equals(request.getUrl().getHost());}
   @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
    if(!"appassets.androidplatform.net".equals(request.getUrl().getHost()))return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));
    String path=request.getUrl().getPath().substring(1);if(path.contains(".."))return null;
    try{
     if(path.startsWith("models/")||path.startsWith("local-audio/")){
      File root=new File(getFilesDir(),path.startsWith("models/")?"models":"audio"),file=new File(root,path.substring(path.indexOf('/')+1));
      if(!file.getCanonicalPath().startsWith(root.getCanonicalPath()+File.separator)||!file.isFile())throw new IOException("Not found");
      String type=path.endsWith(".json")?"application/json":path.endsWith(".wav")?"audio/wav":path.endsWith(".png")?"image/png":path.endsWith(".jpg")?"image/jpeg":"application/octet-stream";
      return new WebResourceResponse(type,null,new FileInputStream(file));
     }
     if(path.equals("api/models/bone-repairs")&&request.getMethod().equals("GET"))return new WebResourceResponse("application/json","UTF-8",new ByteArrayInputStream("{\"repairs\":null}".getBytes("UTF-8")));
     if(path.startsWith("api/"))return new WebResourceResponse("application/json","UTF-8",404,"Not available",null,new ByteArrayInputStream("{}".getBytes("UTF-8")));
    }catch(Exception error){return new WebResourceResponse("text/plain","UTF-8",404,"Not found",null,new ByteArrayInputStream(new byte[0]));}
    String mime=path.endsWith(".css")?"text/css":path.endsWith(".wasm")?"application/wasm":path.endsWith(".js")||path.endsWith(".mjs")?"application/javascript":path.endsWith(".html")?"text/html":path.endsWith(".png")?"image/png":"application/octet-stream";
    try{return new WebResourceResponse(mime,"UTF-8",getAssets().open(path));}catch(IOException error){return new WebResourceResponse("text/plain","UTF-8",404,"Not found",null,new ByteArrayInputStream(new byte[0]));}
   }
  });
  web.setWebChromeClient(new WebChromeClient(){@Override public void onPermissionRequest(PermissionRequest request){runOnUiThread(()->{
   if(!"appassets.androidplatform.net".equals(request.getOrigin().getHost())){request.deny();return;}
   cameraRequest=request;if(checkSelfPermission(Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED)grantCamera();else requestPermissions(new String[]{Manifest.permission.CAMERA},1);
  });}});
  web.loadUrl("https://appassets.androidplatform.net/index.html");
 }
 private void grantCamera(){if(cameraRequest!=null){cameraRequest.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});cameraRequest=null;}}
 @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){super.onRequestPermissionsResult(code,permissions,results);if(code==7){wakePermissionPending=false;String id=wakePermissionId;wakePermissionId=null;if(id!=null)startWake(id);return;}if(code==6){if(microphone!=null)microphone.permissionResult();return;}if(code==5){if(locations!=null)locations.permissionsResult();return;}if(code==3){if(calls!=null)calls.permissions();return;}if(code==1&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)grantCamera();else if(cameraRequest!=null){cameraRequest.deny();cameraRequest=null;}}
 class Bridge {
  private void complete(String id,String result){web.post(()->web.evaluateJavascript("window.sakuraNativeReply?.("+JSONObject.quote(id)+","+result+")",null));}
  @JavascriptInterface public String wakeState(){return MainActivity.this.wakeState();}
  @JavascriptInterface public void installWakePack(String id){new Thread(()->{try{if(WakeAssets.downloading)throw new Exception("A wake pack download is already running.");WakeAssets.downloading=true;WakeAssets.install(MainActivity.this,message->{WakeAssets.downloadStatus=message;});WakeAssets.downloadStatus="Wake pack ready";complete(id,MainActivity.this.wakeState());}catch(Exception error){WakeAssets.downloadStatus=error.getMessage();complete(id,error(error));}finally{WakeAssets.downloading=false;}}).start();}
  @JavascriptInterface public void setWake(String id,boolean enabled,String phrase){runOnUiThread(()->{try{
   if(!enabled){stopService(new Intent(MainActivity.this,WakeService.class));web.postDelayed(()->complete(id,MainActivity.this.wakeState()),200);return;}
   if(!phoneForeground)throw new Exception("Open Sakura to enable background listening.");
   if(!WakeAssets.ready(MainActivity.this))throw new Exception("Download the offline wake pack first.");
   if(prefs().getString("local-key","").isEmpty()||MobileModels.list(new File(getFilesDir(),"models")).length()==0)throw new Exception("Save your API key and at least one model before enabling wake mode.");
   String value=WakePhrase.validate(phrase);if(WakeService.live!=null&&!value.equals(prefs().getString("wake-phrase","hey sakura")))throw new Exception("Turn wake listening off before changing its phrase.");prefs().edit().putString("wake-phrase",value).apply();
   java.util.ArrayList<String> missing=new java.util.ArrayList<>();if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)missing.add(Manifest.permission.RECORD_AUDIO);if(android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)missing.add(Manifest.permission.POST_NOTIFICATIONS);
   if(!missing.isEmpty()){wakePermissionId=id;wakePermissionPending=true;requestPermissions(missing.toArray(new String[0]),7);}else startWake(id);
  }catch(Exception error){complete(id,error(error));}});}
  @JavascriptInterface public void setAssistantState(boolean ready,boolean busy){assistantReady=ready;WakeService.busy(busy);}
  @JavascriptInterface public void syncWakeHistory(String history){try{JSONArray messages=new JSONArray(history);if(history.length()>100000||messages.length()>20)return;prefs().edit().putString("wake-history",history).putLong("wake-history-time",System.currentTimeMillis()).apply();}catch(Exception ignored){}}
  @JavascriptInterface public String wakeHistory(){try{return new JSONObject().put("messages",new JSONArray(prefs().getString("wake-history","[]"))).put("updated_at",prefs().getLong("wake-history-time",0)).toString();}catch(Exception error){return "{}";}}
  @JavascriptInterface public void setModelFullscreen(boolean enabled){if(localAvailable)runOnUiThread(()->fullscreen(enabled));}
  @JavascriptInterface public void setMicrophone(boolean enabled){if(!localAvailable)return;runOnUiThread(()->{final int request=++microphoneGeneration;if(!enabled){microphone.stop();microphone.state(false,"Microphone off");return;}if(calls!=null&&calls.inCall()){microphone.state(false,"Sakura is muted during your call.");return;}WakeService.pauseManual(true);new Thread(()->{long end=android.os.SystemClock.elapsedRealtime()+2000;while(WakeService.recording()&&android.os.SystemClock.elapsedRealtime()<end)try{Thread.sleep(20);}catch(InterruptedException ignored){}runOnUiThread(()->{if(request==microphoneGeneration&&phoneForeground)microphone.start();else if(request==microphoneGeneration)WakeService.pauseManual(false);});}).start();});}
  @JavascriptInterface public boolean localAvailable(){return localAvailable;}
  @JavascriptInterface public String locationState(){try{return locations==null?"{\"enabled\":false}":locations.state().toString();}catch(Exception error){return error(error);}}
  @JavascriptInterface public void openPlace(double latitude,double longitude){if(!localAvailable||!Double.isFinite(latitude)||!Double.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180)return;runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://www.google.com/maps/search/?api=1&query="+latitude+","+longitude)));}catch(Exception error){phoneNotice("No maps/browser app was available to open this place.");}});}
  @JavascriptInterface public void searchPlaces(double latitude,double longitude,String query){if(!localAvailable||!Double.isFinite(latitude)||!Double.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180||query==null||query.length()>200)return;runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("geo:"+latitude+","+longitude+"?q="+android.net.Uri.encode(query)+"&z=15")));}catch(Exception error){try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://www.google.com/maps/search/?api=1&query="+android.net.Uri.encode(query+" near "+latitude+","+longitude))));}catch(Exception ignored){phoneNotice("No maps/browser app was available.");}}});}
  @JavascriptInterface public void openNearby(double latitude,double longitude){if(!localAvailable||!Double.isFinite(latitude)||!Double.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180)return;runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("geo:"+latitude+","+longitude+"?q=restaurants&z=15")));}catch(Exception error){try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://www.google.com/maps/search/restaurants/@"+latitude+","+longitude+",15z")));}catch(Exception ignored){phoneNotice("No maps/browser app was available.");}}});}
  @JavascriptInterface public void setLocation(String id,boolean enabled){new Thread(()->{try{
   if(!localAvailable||locations==null)throw new Exception("Location belongs to Sakura Mobile Local mode.");
   if(enabled){locations.setting("ask");locations.current(true);}else{locations.setting("off");locations.stop();}
   complete(id,locations.state().toString());
  }catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void dictate(){if(!localAvailable)return;runOnUiThread(()->{try{
   if(calls!=null&&calls.inCall())throw new Exception("Sakura is muted during your call.");
   WakeService.pauseManual(true);dictationPending=true;
   Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_PROMPT,"Speak your message to Sakura");startActivityForResult(intent,4);
  }catch(Exception error){dictationPending=false;WakeService.pauseManual(false);phoneNotice("Phone speech input is unavailable. You can type your message instead.");}});}
  @JavascriptInterface public String setHonorific(String address){try{if(!localAvailable||!address.matches("sir|maam|none"))throw new Exception("Choose Sir, Ma’am or No title.");prefs().edit().putString("local-address",address).apply();return localConfig();}catch(Exception error){return error(error);}}
  @JavascriptInterface public String setNewsArea(String area){try{if(!localAvailable||area==null||area.length()>100)throw new Exception("Enter a city or state of up to 100 characters.");prefs().edit().putString("news-area",area.trim()).apply();return localConfig();}catch(Exception error){return error(error);}}
  @JavascriptInterface public String localConfig(){try{return new JSONObject().put("provider",prefs().getString("local-provider","gemini")).put("model",prefs().getString("local-model","gemini-flash-latest")).put("voice",prefs().getString("local-voice","female")).put("address",prefs().getString("local-address","sir")).put("news_area",prefs().getString("news-area","")).put("key_set",!prefs().getString("local-key","").isEmpty()).toString();}catch(Exception error){return error(error);}}
  @JavascriptInterface public String configureLocal(String provider,String key,String model,String voice,String address){try{
   if(!localAvailable)throw new Exception("Local mode belongs to Sakura Mobile.");
   if(key.length()>4096||key.contains("\r")||key.contains("\n"))throw new Exception("Enter a valid API key.");
   if(!provider.matches("gemini|openai")||!model.matches("[A-Za-z0-9_.-]{1,100}")||!voice.matches("male|female")||!address.matches("sir|maam|none"))throw new Exception("Choose valid provider, model and voice settings.");
   String previous=prefs().getString("local-provider","");SharedPreferences.Editor editor=prefs().edit();
   if(!key.trim().isEmpty())editor.putString("local-key",protect(key.trim()));else if(!previous.isEmpty()&&!previous.equals(provider))throw new Exception("Enter a key when changing providers.");
   editor.putString("local-provider",provider).putString("local-model",model).putString("local-voice",voice).putString("local-address",address).apply();return localConfig();
  }catch(Exception error){return error(error);}}
  @JavascriptInterface public void localChat(String id,String history){new Thread(()->{try{
   if(!localAvailable)throw new Exception("Local mode unavailable.");if(calls!=null&&calls.inCall())throw new Exception("Sakura is muted during your call.");if(history.length()>100000)throw new Exception("Conversation too large.");
   String encrypted=prefs().getString("local-key","");if(encrypted.isEmpty())throw new Exception("Add your API key in Local settings.");
   JSONObject result=new PhoneAssistant(MainActivity.this).reply(new JSONArray(history),prefs().getString("local-provider","gemini"),unprotect(encrypted),prefs().getString("local-model","gemini-flash-latest"),prefs().getString("local-address","sir"));complete(id,result.toString());
  }catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void localSpeak(String id,String text){new Thread(()->{try{
   if(!localAvailable)throw new Exception("Local mode unavailable.");if(calls!=null&&calls.inCall())throw new Exception("Sakura is muted during your call.");String encrypted=prefs().getString("local-key","");if(encrypted.isEmpty())throw new Exception("Add an API key for cloud voices.");
   String audio=new PhoneAssistant(MainActivity.this).speech(text,prefs().getString("local-provider","gemini"),unprotect(encrypted),prefs().getString("local-voice","female"),new File(getFilesDir(),"audio"));complete(id,new JSONObject().put("audio",audio).toString());
  }catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public String localModels(){try{return localAvailable?MobileModels.list(new File(getFilesDir(),"models")).toString():"[]";}catch(Exception error){return "[]";}}
  @JavascriptInterface public void modelCatalog(String id){new Thread(()->{try{
   if(!localAvailable)throw new Exception("Local mode unavailable.");String encrypted=prefs().getString("local-key","");if(encrypted.isEmpty())throw new Exception("Enter and save your provider API key first.");
   String provider=prefs().getString("local-provider","gemini");complete(id,new JSONObject().put("models",PhoneAssistant.models(provider,unprotect(encrypted))).put("provider",provider).toString());
  }catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void checkLocalApi(String id){new Thread(()->{try{
   if(!localAvailable)throw new Exception("Local mode unavailable.");String encrypted=prefs().getString("local-key","");if(encrypted.isEmpty())throw new Exception("Enter and save your provider API key first.");
   complete(id,new PhoneAssistant(MainActivity.this).check(prefs().getString("local-provider","gemini"),unprotect(encrypted),prefs().getString("local-model","gemini-flash-latest")).toString());
  }catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void receiveModel(String id,String requestId){new Thread(()->{try{
   if(!localAvailable)throw new Exception("Local mode unavailable.");JSONObject state=new JSONObject(call("GET","/state","{}")),transfer=state.optJSONObject("transfer_request");
   if(transfer==null||!transfer.optString("id").equals(requestId)||!transfer.optString("status").equals("ready"))throw new Exception("The requested transfer is not ready.");
   JSONObject model=transfer.getJSONObject("model"),received;
   try{received=MobileModels.receive(base,token,model,new File(getFilesDir(),"models"));}
   catch(Exception failure){try{call("POST","/command",new JSONObject().put("type","model-result").put("request_id",requestId).put("model_id",model.getString("id")).put("status","failed").put("error",failure.getMessage()).toString());}catch(Exception ignored){}throw failure;}
   try{JSONObject ack=new JSONObject(call("POST","/command",new JSONObject().put("type","model-result").put("request_id",requestId).put("model_id",model.getString("id")).put("status","received").toString()));received.put("transfer_acknowledged",ack.optBoolean("ok"));}catch(Exception ignored){received.put("transfer_acknowledged",false);}
   complete(id,received.toString());
  }catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void phoneState(String id){new Thread(()->{try{complete(id,call("GET","/state","{}"));}catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void requestModelTransfer(String id){new Thread(()->{try{if(!localAvailable)throw new Exception("Local mode unavailable.");complete(id,call("POST","/command",new JSONObject().put("type","request-model").toString()));}catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void cancelModelTransfer(String id,String requestId){new Thread(()->{try{if(!localAvailable)throw new Exception("Local mode unavailable.");complete(id,call("POST","/command",new JSONObject().put("type","cancel-model").put("request_id",requestId).toString()));}catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void connectAsync(String id,String address,String code){new Thread(()->complete(id,connect(address,code))).start();}
  @JavascriptInterface public void reconnectAsync(String id,String address){new Thread(()->complete(id,reconnect(address))).start();}
  private SharedPreferences prefs(){return getSharedPreferences("paired-pcs",MODE_PRIVATE);}
  private SecretKey pairingKey()throws Exception{
   KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
   if(!store.containsAlias("SakuraPairing")){KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");generator.init(new KeyGenParameterSpec.Builder("SakuraPairing",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());generator.generateKey();}
   return (SecretKey)store.getKey("SakuraPairing",null);
  }
  private String protect(String value)throws Exception{Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,pairingKey());return Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(value.getBytes("UTF-8")),Base64.NO_WRAP);}
  private String unprotect(String value)throws Exception{String[] parts=value.split(":",2);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,pairingKey(),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));return new String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),"UTF-8");}
  private void setAddress(String address)throws Exception{
   URI uri=new URI(address);String host=uri.getHost();
   if(!"http".equals(uri.getScheme())||host==null||!host.matches("[0-9.]+"))throw new Exception("Enter the PC's home-network IPv4 link.");
   if(!InetAddress.getByName(host).isSiteLocalAddress())throw new Exception("Use a private home-network address.");
   base="http://"+host+":"+(uri.getPort()>0?uri.getPort():8771);token="";
  }
  @JavascriptInterface public String remembered(){return prefs().getString("computers","[]");}
  @JavascriptInterface public String reconnect(String address){try{setAddress(address);JSONArray list=new JSONArray(remembered());for(int i=0;i<list.length();i++){JSONObject pc=list.getJSONObject(i);if(base.equals(pc.getString("address"))){token=unprotect(pc.getString("credential"));JSONObject state=new JSONObject(call("GET","/state","{}"));if(state.has("error")){token="";return state.toString();}return new JSONObject().put("name",pc.optString("name","Sakura")).put("edition",state.optString("edition","companion")).toString();}}throw new Exception("Pair this PC as a new device first.");}catch(Exception error){token="";return error(error);}}
  @JavascriptInterface public String connect(String address,String code){
   try{setAddress(address);String id=prefs().getString("device-id","");if(id.isEmpty()){id=java.util.UUID.randomUUID().toString();prefs().edit().putString("device-id",id).apply();}
    String response=call("POST","/pair",new JSONObject().put("code",code).put("device_id",id).put("device_name",android.os.Build.MANUFACTURER+" "+android.os.Build.MODEL).toString());JSONObject data=new JSONObject(response);if(data.has("token")){token=data.getString("token");JSONArray old=new JSONArray(remembered()),list=new JSONArray();for(int i=0;i<old.length();i++)if(!base.equals(old.getJSONObject(i).optString("address")))list.put(old.getJSONObject(i));list.put(new JSONObject().put("address",base).put("name",data.optString("name","Sakura")).put("credential",protect(token)));prefs().edit().putString("computers",list.toString()).apply();}return response;
   }catch(Exception error){return error(error);}
  }
  @JavascriptInterface public void trackingStateAsync(String id){new Thread(()->{try{complete(id,call("GET","/state","{}"));}catch(Exception e){complete(id,error(e));}},"SakuraTrackingState").start();}
  @JavascriptInterface public void trackingFrameAsync(String id,String body){
   new Thread(()->{try{
    if(body.length()>180000)throw new IOException("Tracking packet too large");
    complete(id,call("POST","/frame",body));
   }catch(Exception error){complete(id,error(error));}},"SakuraTrackingUpload").start();
  }
  @JavascriptInterface public String request(String method,String path,String body){
    if(!path.matches("/(state|command|frame|camera|chat|gemini|tools)"))return "{\"error\":\"Unsupported request\"}";
   try{return call(method,path,body);}catch(Exception error){return error(error);}
  }
  private String call(String method,String path,String body)throws Exception{
   if(base.isEmpty())throw new Exception("Connect to your PC first.");
   HttpURLConnection connection=(HttpURLConnection)new URL(base+path).openConnection();connection.setInstanceFollowRedirects(false);
   connection.setConnectTimeout(path.equals("/frame")?1000:5000);connection.setReadTimeout(path.equals("/frame")?1000:path.equals("/chat")?120000:10000);connection.setRequestMethod(method);
   connection.setRequestProperty("Content-Type","application/json");if(!token.isEmpty())connection.setRequestProperty("Authorization","Bearer "+token);
   try{if(method.equals("POST")){connection.setDoOutput(true);try(OutputStream output=connection.getOutputStream()){output.write(body.getBytes("UTF-8"));}}
    InputStream input=connection.getResponseCode()<400?connection.getInputStream():connection.getErrorStream();if(input==null)throw new IOException("PC connection failed.");
    ByteArrayOutputStream output=new ByteArrayOutputStream();try(InputStream stream=input){byte[] buffer=new byte[8192];int n;while((n=stream.read(buffer))!=-1){output.write(buffer,0,n);if(output.size()>2000000)throw new IOException("Response too large");}}return output.toString("UTF-8");
   }finally{connection.disconnect();}
  }
  private String error(Exception error){try{return new JSONObject().put("error",error.getMessage()).toString();}catch(Exception ignored){return "{}";}}
 }
 @Override protected void onPause(){super.onPause();microphoneGeneration++;if(microphone!=null)microphone.pause();boolean locationPrompt=(locations!=null&&locations.awaitingPermission)||(microphone!=null&&microphone.permissionPending)||wakePermissionPending;if(!locationPrompt){phoneForeground=false;if(locations!=null)locations.stop();}if(web!=null)web.evaluateJavascript("window.stopPhoneTracking?.();window.stopPhoneVision?.();"+(locationPrompt?"":"window.sakuraLocalPause?.()"),null);}
 @Override protected void onStop(){super.onStop();if(microphone!=null){microphone.stop();microphone.state(false,"Microphone off");}phoneForeground=false;WakeService.busy(false);if(web!=null){web.onPause();web.pauseTimers();}if(locations!=null)locations.stop();}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==4){dictationPending=false;WakeService.pauseManual(false);}if(request==4&&result==RESULT_OK&&data!=null){java.util.ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty())web.evaluateJavascript("window.sakuraDictation?.("+JSONObject.quote(words.get(0))+")",null);}}
 @Override protected void onResume(){super.onResume();phoneForeground=true;if(web!=null){web.resumeTimers();web.onResume();}if(microphone!=null)microphone.resume();if(calls!=null)calls.resume();if(web!=null)web.evaluateJavascript("window.sakuraResume?.()",null);}
 @Override protected void onDestroy(){if(current.get()==this)current.clear();if(microphone!=null)microphone.stop();if(calls!=null)calls.close();if(web!=null){web.removeJavascriptInterface("Sakura");web.destroy();}super.onDestroy();}
}
