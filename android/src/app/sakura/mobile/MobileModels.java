package app.sakura.mobile;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;
import org.json.*;

final class MobileModels {
 static JSONArray list(File root)throws Exception{
  JSONArray result=new JSONArray();File[] folders=root.listFiles();if(folders==null)return result;
  for(File folder:folders){File info=new File(folder,"sakura-mobile-model.json");if(!folder.getName().matches("[a-f0-9]{32}")||!info.isFile())continue;try{JSONObject item=new JSONObject(read(info));item.put("id",folder.getName());item.put("url","/models/"+folder.getName()+"/"+item.getString("entry"));result.put(item);}catch(Exception ignored){}}
  return result;
 }
 static String read(File file)throws Exception{try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>1000000)throw new IOException("Metadata too large");}return out.toString("UTF-8");}}
 static void remove(File file){if(file.isDirectory()){File[] children=file.listFiles();if(children!=null)for(File child:children)remove(child);}file.delete();}
 static JSONObject receive(String base,String token,String pin,JSONObject metadata,File root)throws Exception{
  String id=metadata.getString("id"),digest=metadata.getString("sha256");if(!id.matches("[a-f0-9]{32}")||!digest.matches("[a-f0-9]{64}"))throw new IOException("Invalid transfer metadata");
  root.mkdirs();File stage=new File(root,"incoming-"+UUID.randomUUID()),archive=File.createTempFile("transfer-",".zip",root);stage.mkdirs();
  HttpURLConnection connection=(HttpURLConnection)new URL(base+"/model/package/"+id).openConnection();connection.setInstanceFollowRedirects(false);connection.setRequestProperty("Authorization","Bearer "+token);connection.setConnectTimeout(10000);connection.setReadTimeout(120000);
  if(connection instanceof javax.net.ssl.HttpsURLConnection){javax.net.ssl.HttpsURLConnection secure=(javax.net.ssl.HttpsURLConnection)connection;secure.setSSLSocketFactory(PcTls.factory(pin));secure.setHostnameVerifier(PcTls.verifier());}
  try{
   int status=connection.getResponseCode();
   if(status!=200)throw new IOException("PC model transfer is no longer available. Send it again.");
   if(!pin.equals(PcTls.presented(connection)))throw new IOException("The PC's certificate changed during the model transfer.");
   MessageDigest sha=MessageDigest.getInstance("SHA-256");long bytes=0;
   try(InputStream in=connection.getInputStream();OutputStream out=new FileOutputStream(archive)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){bytes+=n;if(bytes>500000000)throw new IOException("Transfer exceeds 500 MB");sha.update(b,0,n);out.write(b,0,n);}}
   StringBuilder actual=new StringBuilder();for(byte value:sha.digest())actual.append(String.format(Locale.ROOT,"%02x",value&255));if(bytes!=metadata.getLong("bytes")||!actual.toString().equals(digest))throw new IOException("Model checksum mismatch. Send it again.");
   long expanded=0;int files=0;Set<String> names=new HashSet<>();
   try(ZipInputStream zip=new ZipInputStream(new FileInputStream(archive))){ZipEntry entry;byte[] b=new byte[65536];while((entry=zip.getNextEntry())!=null){
    String name=entry.getName();File target=new File(stage,name);if(name.contains("\\")||name.startsWith("/")||!target.getCanonicalPath().startsWith(stage.getCanonicalPath()+File.separator)||!names.add(name)||++files>2501)throw new IOException("Unsafe model archive");
    if(entry.isDirectory()){target.mkdirs();continue;}target.getParentFile().mkdirs();try(OutputStream out=new FileOutputStream(target)){int n;while((n=zip.read(b))!=-1){expanded+=n;if(expanded>1000000000)throw new IOException("Expanded model exceeds 1 GB");out.write(b,0,n);}}
   }}
   JSONObject model=new JSONObject(read(new File(stage,"sakura-mobile-model.json")));String entry=model.getString("entry");File main=new File(stage,entry);if(!main.isFile()||!main.getCanonicalPath().startsWith(stage.getCanonicalPath()+File.separator)||!entry.equals(metadata.getString("entry"))||!model.getString("format").matches("pmx|vrm|live2d"))throw new IOException("Model entry point is missing");
   File destination=new File(root,id);if(destination.exists())throw new IOException("This model is already received. Choose it in the list.");if(!stage.renameTo(destination))throw new IOException("Not enough storage to finish importing model");
   model.put("id",id).put("url","/models/"+id+"/"+entry);return model;
  }finally{connection.disconnect();archive.delete();remove(stage);}
 }
}
