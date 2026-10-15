package app.sakura.mobile;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.*;
import android.content.pm.PackageManager;
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
 private WebView web; private String base="",token=""; private PermissionRequest cameraRequest;
 @Override public void onCreate(Bundle state){
  super.onCreate(state); web=new WebView(this);setContentView(web);
  web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);
  web.getSettings().setMediaPlaybackRequiresUserGesture(false);
  web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);
  web.addJavascriptInterface(new Bridge(),"Sakura");
  web.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !request.getUrl().getHost().equals("appassets.androidplatform.net");}
   @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
    if(!"appassets.androidplatform.net".equals(request.getUrl().getHost()))return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));
    String path=request.getUrl().getPath().substring(1);if(path.contains(".."))return null;
    String mime=path.endsWith(".wasm")?"application/wasm":path.endsWith(".js")||path.endsWith(".mjs")?"application/javascript":path.endsWith(".html")?"text/html":path.endsWith(".png")?"image/png":"application/octet-stream";
    try{return new WebResourceResponse(mime,"UTF-8",getAssets().open(path));}catch(IOException error){return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));}
   }
  });
  web.setWebChromeClient(new WebChromeClient(){@Override public void onPermissionRequest(PermissionRequest request){runOnUiThread(()->{
   if(!"appassets.androidplatform.net".equals(request.getOrigin().getHost())){request.deny();return;}
   cameraRequest=request;if(checkSelfPermission(Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED)grantCamera();else requestPermissions(new String[]{Manifest.permission.CAMERA},1);
  });}});
  web.loadUrl("https://appassets.androidplatform.net/index.html");
 }
 private void grantCamera(){if(cameraRequest!=null){cameraRequest.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});cameraRequest=null;}}
 @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){super.onRequestPermissionsResult(code,permissions,results);if(code==1&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)grantCamera();else if(cameraRequest!=null){cameraRequest.deny();cameraRequest=null;}}
 class Bridge {
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
 @Override protected void onPause(){super.onPause();if(web!=null)web.evaluateJavascript("window.stopPhoneTracking?.();window.stopPhoneVision?.()",null);}
 @Override protected void onDestroy(){if(web!=null){web.removeJavascriptInterface("Sakura");web.destroy();}super.onDestroy();}
}
