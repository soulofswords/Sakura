package app.sakura.mobile;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.regex.*;

/** Persistent partial file; exact size and SHA-256 are mandatory before installation. */
final class ResumableDownload {
 interface Progress{void update(String message);}
 static void fetch(String url,File partial,long expected,String hash,int timeout,Progress progress)throws Exception{
  if(partial.length()>expected)partial.delete();
  IOException last=null;
  for(int attempt=0;attempt<5;attempt++){
   long offset=partial.length();
   if(offset==expected){if(verified(partial,hash))return;partial.delete();offset=0;}
   HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(timeout);c.setReadTimeout(timeout);c.setRequestProperty("Accept-Encoding","identity");if(offset>0)c.setRequestProperty("Range","bytes="+offset+"-");
   try{
    progress.update((offset>0?"Resuming":"Connecting")+" offline wake pack · "+String.format(Locale.ROOT,"%.1f / %.1f MB",offset/1000000.0,expected/1000000.0));
    int code=c.getResponseCode();boolean append=false;
    if(code==206){Matcher range=Pattern.compile("bytes (\\d+)-(\\d+)/(\\d+)").matcher(String.valueOf(c.getHeaderField("Content-Range")));if(!range.matches()||Long.parseLong(range.group(1))!=offset||Long.parseLong(range.group(3))!=expected)throw new IOException("The server returned an invalid resume range.");append=offset>0;}
    else if(code==200){if(offset>0)progress.update("This server cannot resume · restarting this attempt");offset=0;}
    else throw new IOException("Wake pack server returned HTTP "+code+".");
    long total=offset,mark=System.currentTimeMillis(),lastBytes=offset;
    try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(partial,append)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1){total+=n;if(total>expected)throw new IOException("Wake pack exceeded its expected size.");out.write(buffer,0,n);long now=System.currentTimeMillis();if(now-mark>=500){long speed=(total-lastBytes)*1000/Math.max(1,now-mark);progress.update(String.format(Locale.ROOT,"Downloading wake pack · %.1f / %.1f MB · %d%% · %d KB/s",total/1000000.0,expected/1000000.0,total*100/expected,speed/1000));mark=now;lastBytes=total;}}}
    if(partial.length()!=expected)throw new IOException("Connection ended before the download completed.");
    progress.update("Download complete · checking integrity…");if(!verified(partial,hash)){partial.delete();throw new IOException("Wake pack integrity failed; corrupted partial file discarded.");}return;
   }catch(IOException error){last=error;progress.update("Connection interrupted · "+String.format(Locale.ROOT,"%.1f MB saved",partial.length()/1000000.0)+" · retry "+(attempt+1)+"/5");}
   finally{c.disconnect();}
   if(attempt<4)Thread.sleep(Math.min(4000,500L*(attempt+1)));
  }
  throw new IOException("Download paused at "+String.format(Locale.ROOT,"%.1f MB",partial.length()/1000000.0)+". Tap Resume download to continue. "+(last==null?"":last.getMessage()));
 }
 static boolean verified(File file,String expected)throws Exception{MessageDigest sha=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)sha.update(b,0,n);}StringBuilder digest=new StringBuilder();for(byte b:sha.digest())digest.append(String.format(Locale.ROOT,"%02x",b&255));return expected.equals(digest.toString());}
}
