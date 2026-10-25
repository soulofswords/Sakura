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

 private PhoneMicrophone microphone;private boolean modelFullscreen;private int microphoneGeneration;private boolean dictationPending;private String modelImportJob;
 void microphoneEvent(boolean on,String message,String text){if(!on&&!dictationPending)WakeService.pauseManual(false);if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraMicrophone?.("+on+","+JSONObject.quote(message)+","+(text==null?"null":JSONObject.quote(text))+")",null));}
 private void fullscreen(boolean enabled){modelFullscreen=enabled;android.view.View decor=getWindow().getDecorView();if(android.os.Build.VERSION.SDK_INT>=30){getWindow().setDecorFitsSystemWindows(!enabled);android.view.WindowInsetsController controller=decor.getWindowInsetsController();if(controller!=null){controller.setSystemBarsBehavior(android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);if(enabled)controller.hide(android.view.WindowInsets.Type.systemBars());else controller.show(android.view.WindowInsets.Type.systemBars());}}else decor.setSystemUiVisibility(enabled?android.view.View.SYSTEM_UI_FLAG_FULLSCREEN|android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|android.view.View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE:android.view.View.SYSTEM_UI_FLAG_VISIBLE);}
 @Override public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(focus&&modelFullscreen)fullscreen(true);}
 @Override public void onBackPressed(){if(modelFullscreen&&web!=null)web.evaluateJavascript("window.sakuraExitModelFullscreen?.()",null);else super.onBackPressed();}
 PhoneLocation locations;volatile boolean phoneForeground=false;
 void callState(boolean active){if(active&&microphone!=null)runOnUiThread(()->{microphone.stop();microphone.state(false,"Call in progress · microphone off");});if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraCallState?.("+active+")",null));}
 void phoneNotice(String text){if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraPhoneNotice?.("+JSONObject.quote(text)+")",null));}
 void requestCall(String person){if(localAvailable&&calls!=null)calls.request(person);}
 private WebView web; private volatile String base="",token="",pin="",lastFingerprint=""; private PermissionRequest cameraRequest;
 private PhoneTrackingSender trackingSender;
 private synchronized void stopTrackingSender(){if(trackingSender!=null){trackingSender.close();trackingSender=null;}}
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
  @JavascriptInterface public void submitTrackingFrame(String body){
   if(!phoneForeground||body.length()>180000||base.isEmpty()||token.isEmpty())return;
   synchronized(MainActivity.this){if(trackingSender==null)trackingSender=new PhoneTrackingSender(frame->{
    JSONObject result=new JSONObject(call("POST","/frame",frame));if(result.has("error"))throw new IOException(result.optString("error"));
   },(fps,dropped,ms,error)->{if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraTrackingTransport?.("+fps+","+dropped+","+ms+","+JSONObject.quote(error)+")",null));});trackingSender.submit(body);}
  }
  @JavascriptInterface public void stopTrackingFrames(){stopTrackingSender();}
  @JavascriptInterface public void importPhoneModel(String id){runOnUiThread(()->{
   if(modelImportJob!=null){complete(id,error(new Exception("A model picker is already open.")));return;}
   modelImportJob=id;
   try{Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.addCategory(Intent.CATEGORY_OPENABLE);picker.setType("*/*");startActivityForResult(picker,71);}
   catch(Exception e){modelImportJob=null;complete(id,error(e));}
  });}
  @JavascriptInterface public boolean systemDarkAppearance(){return (getResources().getConfiguration().uiMode & android.content.res.Configuration.UI_MODE_NIGHT_MASK)==android.content.res.Configuration.UI_MODE_NIGHT_YES;}
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
   try{received=MobileModels.receive(base,token,pin,model,new File(getFilesDir(),"models"));}
   catch(Exception failure){try{call("POST","/command",new JSONObject().put("type","model-result").put("request_id",requestId).put("model_id",model.getString("id")).put("status","failed").put("error",failure.getMessage()).toString());}catch(Exception ignored){}throw failure;}
   try{JSONObject ack=new JSONObject(call("POST","/command",new JSONObject().put("type","model-result").put("request_id",requestId).put("model_id",model.getString("id")).put("status","received").toString()));received.put("transfer_acknowledged",ack.optBoolean("ok"));}catch(Exception ignored){received.put("transfer_acknowledged",false);}
   complete(id,received.toString());
  }catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void phoneState(String id){new Thread(()->{try{complete(id,call("GET","/state","{}"));}catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void requestModelTransfer(String id){new Thread(()->{try{if(!localAvailable)throw new Exception("Local mode unavailable.");complete(id,call("POST","/command",new JSONObject().put("type","request-model").toString()));}catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void cancelModelTransfer(String id,String requestId){new Thread(()->{try{if(!localAvailable)throw new Exception("Local mode unavailable.");complete(id,call("POST","/command",new JSONObject().put("type","cancel-model").put("request_id",requestId).toString()));}catch(Exception error){complete(id,error(error));}}).start();}
  @JavascriptInterface public void connectAsync(String id,String address,String code,String fingerprint){new Thread(()->complete(id,connect(address,code,fingerprint))).start();}
  @JavascriptInterface public void reconnectAsync(String id,String computerId,String address){new Thread(()->complete(id,reconnect(computerId,address))).start();}
  @JavascriptInterface public void discoverAsync(String id){new Thread(()->{try{complete(id,new JSONObject().put("computers",discover(1800)).toString());}catch(Exception error){complete(id,error(error));}},"SakuraDiscover").start();}
  private SharedPreferences prefs(){return getSharedPreferences("paired-pcs",MODE_PRIVATE);}
  private SecretKey pairingKey()throws Exception{
   KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
   if(!store.containsAlias("SakuraPairing")){KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");generator.init(new KeyGenParameterSpec.Builder("SakuraPairing",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());generator.generateKey();}
   return (SecretKey)store.getKey("SakuraPairing",null);
  }
  private String protect(String value)throws Exception{Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,pairingKey());return Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(value.getBytes("UTF-8")),Base64.NO_WRAP);}
  private String unprotect(String value)throws Exception{String[] parts=value.split(":",2);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,pairingKey(),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));return new String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),"UTF-8");}
  private void setAddress(String address,String fingerprint)throws Exception{
   String text=address==null?"":address.trim();if(!text.contains("://"))text="https://"+text;
   URI uri=new URI(text);String host=uri.getHost();
   if(!"https".equals(uri.getScheme())||host==null||!host.matches("[0-9.]+"))throw new Exception("Enter the encrypted PC link shown in Sakura settings.");
   if(!InetAddress.getByName(host).isSiteLocalAddress())throw new Exception("Use a private home-network address.");
   String candidate=fingerprint==null?"":fingerprint.toLowerCase(java.util.Locale.ROOT);
   if(!candidate.isEmpty()&&!candidate.matches("[0-9a-f]{64}"))throw new Exception("That PC's certificate fingerprint is invalid.");
   base="https://"+host+":"+(uri.getPort()>0?uri.getPort():8771);pin=candidate;token="";
  }
  @JavascriptInterface public String remembered(){return prefs().getString("computers","[]");}
  private JSONArray computers()throws Exception{return new JSONArray(remembered());}
  private void saveComputers(JSONArray list){prefs().edit().putString("computers",list.toString()).apply();}
  // Use the actual interface broadcast, including non-/24 home networks.
  private JSONArray discover(long patienceMillis)throws Exception{
   java.util.LinkedHashSet<String> targets=new java.util.LinkedHashSet<>();targets.add("255.255.255.255");
   java.util.Enumeration<NetworkInterface> interfaces=NetworkInterface.getNetworkInterfaces();
   while(interfaces.hasMoreElements()){NetworkInterface nic=interfaces.nextElement();
    if(!nic.isUp()||nic.isLoopback())continue;
    for(java.net.InterfaceAddress binding:nic.getInterfaceAddresses()){InetAddress address=binding.getAddress();
     if(!(address instanceof Inet4Address)||address.isLoopbackAddress()||!address.isSiteLocalAddress())continue;
     InetAddress broadcast=binding.getBroadcast();if(broadcast!=null)targets.add(broadcast.getHostAddress());}}
   DatagramSocket socket=new DatagramSocket();socket.setBroadcast(true);
   java.util.LinkedHashMap<String,JSONObject> found=new java.util.LinkedHashMap<>();
   try{
    byte[] magic="sakura-discover-v1".getBytes("UTF-8");
    for(String target:targets)try{socket.send(new DatagramPacket(magic,magic.length,InetAddress.getByName(target),8770));}catch(IOException ignored){}
    socket.setSoTimeout(300);byte[] buffer=new byte[2048];long deadline=System.currentTimeMillis()+patienceMillis;
    while(System.currentTimeMillis()<deadline){
     try{DatagramPacket packet=new DatagramPacket(buffer,buffer.length);socket.receive(packet);
      JSONObject reply=new JSONObject(new String(packet.getData(),0,packet.getLength(),"UTF-8"));
      if(!"sakura".equals(reply.optString("service")))continue;
      String identity=reply.optString("id");
      URI endpoint=new URI(reply.optString("https"));
      if(identity.matches("[0-9a-f]{32}")&&reply.optString("fingerprint").matches("[0-9a-f]{64}")&&"https".equals(endpoint.getScheme())&&packet.getAddress().isSiteLocalAddress()
         &&packet.getAddress().getHostAddress().equals(endpoint.getHost())&&endpoint.getPort()>0&&endpoint.getPort()<=65535
         &&endpoint.getRawUserInfo()==null&&(endpoint.getPath()==null||endpoint.getPath().isEmpty())&&endpoint.getQuery()==null&&endpoint.getFragment()==null)found.put(identity,reply);
     }catch(SocketTimeoutException slow){}catch(Exception ignored){}
    }
   }finally{socket.close();}
   JSONArray list=new JSONArray();for(JSONObject reply:found.values())list.put(reply);return list;
  }
  private JSONObject authenticate(String address,String credential,String expectedId,String fingerprint)throws Exception{
   setAddress(address,fingerprint);
   String secret=unprotect(credential);
   byte[] random=new byte[32];new java.security.SecureRandom().nextBytes(random);StringBuilder challenge=new StringBuilder();
   for(byte b:random)challenge.append(String.format(java.util.Locale.ROOT,"%02x",b&255));String nonce=challenge.toString();
   // No bearer token is sent until the PC proves possession of the paired secret.
   JSONObject proof=new JSONObject(call("POST","/identity-proof",new JSONObject().put("device_id",prefs().getString("device-id","")).put("endpoint",base).put("nonce",nonce).toString()));
   if(!base.equals(proof.optString("endpoint"))||!PhoneIdentity.verify(secret,expectedId,proof.optString("pc_id"),base,nonce,proof.optString("nonce"),proof.optString("proof")))throw new Exception("PC identity verification failed. Pair again if the PC was reset.");
   token=secret;
   JSONObject state=new JSONObject(call("GET","/state","{}"));
   if(state.has("error"))throw new Exception(state.optString("error","The PC refused this connection."));
   if(!proof.getString("pc_id").equals(state.optString("pc_id")))throw new Exception("PC identity changed during reconnect.");
   return state;
  }
  private String accepted(JSONArray list,JSONObject record,JSONObject state,String address)throws Exception{
   base=address;
   if(state.has("pc_id"))record.put("id",state.getString("pc_id"));
   record.put("address",address);record.put("fingerprint",pin);
   if(state.has("name"))record.put("name",state.getString("name"));
   if(state.has("edition"))record.put("edition",state.getString("edition"));
   saveComputers(list);
   return new JSONObject().put("name",record.optString("name","Sakura")).put("edition",state.optString("edition","companion")).toString();
  }
  @JavascriptInterface public String reconnect(String computerId,String address){
   try{JSONArray list=computers();JSONObject record=null;
    for(int i=0;i<list.length();i++){JSONObject pc=list.getJSONObject(i);
     if(!computerId.isEmpty()&&computerId.equals(pc.optString("id"))){record=pc;break;}
     if(computerId.isEmpty()&&!address.isEmpty()&&address.equals(pc.optString("address"))){record=pc;break;}}
    if(record==null)throw new Exception("Pair this PC as a new device first.");
    // A record saved before the encrypted link has no pin, so it cannot prove
    // which PC it is talking to. Making the user pair once is the safe upgrade.
    String fingerprint=record.optString("fingerprint","");
    if(!fingerprint.matches("[0-9a-f]{64}"))throw new Exception("Pair this PC again once to enable the encrypted connection.");
    String credential=record.getString("credential");
    java.util.LinkedHashSet<String> candidates=new java.util.LinkedHashSet<>();candidates.add(record.optString("address",""));candidates.add(address);
    for(String candidate:candidates){
     if(candidate==null||candidate.isEmpty())continue;
     try{return accepted(list,record,authenticate(candidate,credential,record.optString("id",""),fingerprint),candidate);}catch(Exception offline){token="";}}
    JSONArray found=discover(1800);
    for(int i=0;i<found.length();i++){JSONObject beacon=found.getJSONObject(i);
     if(!record.optString("id","").isEmpty()&&!record.getString("id").equals(beacon.optString("id")))continue;
     try{JSONObject state=authenticate(beacon.getString("https"),credential,record.optString("id",""),fingerprint);
      if(!state.optString("pc_id","").equals(beacon.optString("id")))throw new Exception("That PC is not the one this phone paired with.");
      return accepted(list,record,state,beacon.getString("https"));
     }catch(Exception refused){token="";}}
    token="";return new JSONObject().put("error","Sakura was not found on this network. Turn on Connect to Phone in PC Settings, then try again.").toString();
   }catch(Exception error){token="";return error(error);}
  }
  @JavascriptInterface public String connect(String address,String code,String fingerprint){
   try{setAddress(address,fingerprint);String id=prefs().getString("device-id","");if(id.isEmpty()){id=java.util.UUID.randomUUID().toString();prefs().edit().putString("device-id",id).apply();}
    String response=call("POST","/pair",new JSONObject().put("code",code).put("device_id",id).put("device_name",android.os.Build.MANUFACTURER+" "+android.os.Build.MODEL).toString());JSONObject data=new JSONObject(response);
    if(data.has("token")){
     String advertised=data.optString("fingerprint","");
     if(!advertised.matches("[0-9a-f]{64}")||!advertised.equals(lastFingerprint))throw new Exception("The PC did not prove the certificate it presented. Pair again.");
     if(!pin.isEmpty()&&!pin.equals(advertised))throw new Exception("The PC's certificate changed since it was found. Check your Wi-Fi and try again.");
     pin=advertised;token=data.getString("token");String identity=data.optString("id","");JSONArray old=computers(),list=new JSONArray();
     for(int i=0;i<old.length();i++){JSONObject pc=old.getJSONObject(i);if(!identity.isEmpty()&&identity.equals(pc.optString("id")))continue;if(!base.equals(pc.optString("address")))list.put(pc);}
     JSONObject saved=new JSONObject().put("address",base).put("fingerprint",pin).put("name",data.optString("name","Sakura")).put("edition",data.optString("edition","companion")).put("credential",protect(token));
     if(!identity.isEmpty())saved.put("id",identity);
     list.put(saved);saveComputers(list);}
    return response;
   }catch(Exception error){pin="";return error(error);}
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
   if(connection instanceof javax.net.ssl.HttpsURLConnection){javax.net.ssl.HttpsURLConnection secure=(javax.net.ssl.HttpsURLConnection)connection;secure.setSSLSocketFactory(PcTls.factory(pin));secure.setHostnameVerifier(PcTls.verifier());}
   connection.setConnectTimeout(path.equals("/frame")?1000:5000);connection.setReadTimeout(path.equals("/frame")?1000:path.equals("/chat")?120000:10000);connection.setRequestMethod(method);
   connection.setRequestProperty("Content-Type","application/json");if(!token.isEmpty())connection.setRequestProperty("Authorization","Bearer "+token);
   try{if(method.equals("POST")){connection.setDoOutput(true);try(OutputStream output=connection.getOutputStream()){output.write(body.getBytes("UTF-8"));}}
    int status=connection.getResponseCode();
    if(connection instanceof javax.net.ssl.HttpsURLConnection){
     lastFingerprint=PcTls.presented(connection);
     if(!pin.isEmpty()&&!pin.equals(lastFingerprint))throw new IOException("The PC's certificate does not match the saved pairing. Check your Wi-Fi.");
    }
    InputStream input=status<400?connection.getInputStream():connection.getErrorStream();if(input==null)throw new IOException("PC connection failed.");
    ByteArrayOutputStream output=new ByteArrayOutputStream();try(InputStream stream=input){byte[] buffer=new byte[8192];int n;while((n=stream.read(buffer))!=-1){output.write(buffer,0,n);if(output.size()>2000000)throw new IOException("Response too large");}}return output.toString("UTF-8");
   }finally{connection.disconnect();}
  }
  private String error(Exception error){try{return new JSONObject().put("error",error.getMessage()).toString();}catch(Exception ignored){return "{}";}}
 }
 @Override protected void onPause(){super.onPause();stopTrackingSender();microphoneGeneration++;if(microphone!=null)microphone.pause();boolean locationPrompt=(locations!=null&&locations.awaitingPermission)||(microphone!=null&&microphone.permissionPending)||wakePermissionPending;if(!locationPrompt){phoneForeground=false;if(locations!=null)locations.stop();}if(web!=null)web.evaluateJavascript("window.stopPhoneTracking?.();window.stopPhoneVision?.();window.sakuraStopLocalTracking?.();"+(locationPrompt?"":"window.sakuraLocalPause?.()"),null);}
 @Override protected void onStop(){super.onStop();if(microphone!=null){microphone.stop();microphone.state(false,"Microphone off");}phoneForeground=false;WakeService.busy(false);if(web!=null){web.onPause();web.pauseTimers();}if(locations!=null)locations.stop();}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==71){String job=modelImportJob;modelImportJob=null;if(job==null)return;if(result!=RESULT_OK||data==null){new Bridge().complete(job,new Bridge().error(new Exception("Import cancelled.")));return;}android.net.Uri uri=data.getData();new Thread(()->{try{String name="model";try(android.database.Cursor cursor=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);}try(InputStream input=getContentResolver().openInputStream(uri)){if(input==null)throw new IOException("Cannot open the selected file.");new Bridge().complete(job,PhoneModelImport.importModel(input,name,new File(getFilesDir(),"models")).toString());}}catch(Exception e){new Bridge().complete(job,new Bridge().error(e));}},"SakuraModelImport").start();return;}if(request==4){dictationPending=false;WakeService.pauseManual(false);}if(request==4&&result==RESULT_OK&&data!=null){java.util.ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty())web.evaluateJavascript("window.sakuraDictation?.("+JSONObject.quote(words.get(0))+")",null);}}
 @Override protected void onResume(){super.onResume();phoneForeground=true;if(web!=null){web.resumeTimers();web.onResume();}if(microphone!=null)microphone.resume();if(calls!=null)calls.resume();if(web!=null)web.evaluateJavascript("window.sakuraResume?.()",null);}
 @Override protected void onDestroy(){stopTrackingSender();if(current.get()==this)current.clear();if(microphone!=null)microphone.stop();if(calls!=null)calls.close();if(web!=null){web.removeJavascriptInterface("Sakura");web.destroy();}super.onDestroy();}
}
