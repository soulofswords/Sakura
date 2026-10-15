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
 void callState(boolean active){if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraCallState?.("+active+")",null));}
 void phoneNotice(String text){if(web!=null)web.post(()->web.evaluateJavascript("window.sakuraPhoneNotice?.("+JSONObject.quote(text)+")",null));}
 void requestCall(String person){if(localAvailable&&calls!=null)calls.request(person);}
 private WebView web; private String base="",token=""; private PermissionRequest cameraRequest;
 @Override public void onCreate(Bundle state){
  super.onCreate(state); web=new WebView(this);setContentView(web);if(localAvailable)calls=new CallController(this);
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
    String mime=path.endsWith(".wasm")?"application/wasm":path.endsWith(".js")||path.endsWith(".mjs")?"application/javascript":path.endsWith(".html")?"text/html":path.endsWith(".png")?"image/png":"application/octet-stream";
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
 @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){super.onRequestPermissionsResult(code,permissions,results);if(code==3){if(calls!=null)calls.permissions();return;}if(code==1&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)grantCamera();else if(cameraRequest!=null){cameraRequest.deny();cameraRequest=null;}}
 class Bridge {
  private void complete(String id,String result){web.post(()->web.evaluateJavascript("window.sakuraNativeReply?.("+JSONObject.quote(id)+","+result+")",null));}
  @JavascriptInterface public boolean localAvailable(){return localAvailable;}
  @JavascriptInterface public void dictate(){if(!localAvailable)return;runOnUiThread(()->{try{
   if(calls!=null&&calls.inCall())throw new Exception("Sakura is muted during your call.");
   Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_PROMPT,"Speak your message to Sakura");startActivityForResult(intent,4);
  }catch(Exception error){phoneNotice("Phone speech input is unavailable. You can type your message instead.");}});}
  @JavascriptInterface public String localConfig(){try{return new JSONObject().put("provider",prefs().getString("local-provider","gemini")).put("model",prefs().getString("local-model","gemini-flash-latest")).put("voice",prefs().getString("local-voice","female")).put("address",prefs().getString("local-address","sir")).put("key_set",!prefs().getString("local-key","").isEmpty()).toString();}catch(Exception error){return error(error);}}
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
  @JavascriptInterface public String request(String method,String path,String body){
    if(!path.matches("/(state|command|frame|camera|chat|gemini)"))return "{\"error\":\"Unsupported request\"}";
   try{return call(method,path,body);}catch(Exception error){return error(error);}
  }
  private String call(String method,String path,String body)throws Exception{
   if(base.isEmpty())throw new Exception("Connect to your PC first.");
   HttpURLConnection connection=(HttpURLConnection)new URL(base+path).openConnection();connection.setInstanceFollowRedirects(false);
   connection.setConnectTimeout(5000);connection.setReadTimeout(path.equals("/chat")?120000:10000);connection.setRequestMethod(method);
   connection.setRequestProperty("Content-Type","application/json");if(!token.isEmpty())connection.setRequestProperty("Authorization","Bearer "+token);
   try{if(method.equals("POST")){connection.setDoOutput(true);try(OutputStream output=connection.getOutputStream()){output.write(body.getBytes("UTF-8"));}}
    InputStream input=connection.getResponseCode()<400?connection.getInputStream():connection.getErrorStream();if(input==null)throw new IOException("PC connection failed.");
    ByteArrayOutputStream output=new ByteArrayOutputStream();try(InputStream stream=input){byte[] buffer=new byte[8192];int n;while((n=stream.read(buffer))!=-1){output.write(buffer,0,n);if(output.size()>2000000)throw new IOException("Response too large");}}return output.toString("UTF-8");
   }finally{connection.disconnect();}
  }
  private String error(Exception error){try{return new JSONObject().put("error",error.getMessage()).toString();}catch(Exception ignored){return "{}";}}
 }
 @Override protected void onPause(){super.onPause();if(web!=null)web.evaluateJavascript("window.stopPhoneTracking?.();window.stopPhoneVision?.();window.sakuraLocalPause?.()",null);}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==4&&result==RESULT_OK&&data!=null){java.util.ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty())web.evaluateJavascript("window.sakuraDictation?.("+JSONObject.quote(words.get(0))+")",null);}}
 @Override protected void onResume(){super.onResume();if(calls!=null)calls.resume();if(web!=null)web.evaluateJavascript("window.sakuraResume?.()",null);}
 @Override protected void onDestroy(){if(calls!=null)calls.close();if(web!=null){web.removeJavascriptInterface("Sakura");web.destroy();}super.onDestroy();}
}
