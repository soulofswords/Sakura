package app.sakura.mobile;
import android.content.Context;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.zip.*;

final class WakeAssets {
 static final java.util.concurrent.atomic.AtomicBoolean downloading=new java.util.concurrent.atomic.AtomicBoolean();static volatile String downloadStatus="";
 static final String HASH="30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498";
 static File model(Context c){return new File(c.getFilesDir(),"wake/vosk-model-small-en-us-0.15");}
 static boolean ready(Context c){File d=model(c);return new File(d,"ready.sha256").isFile()&&new File(d,"am/final.mdl").isFile()&&new File(d,"graph/Gr.fst").isFile();}
 interface Progress{void update(String message);}
 static synchronized void install(Context context,Progress progress)throws Exception{
  if(ready(context))return;
  File zip=new File(context.getCacheDir(),"wake-model.download");File staging=new File(context.getFilesDir(),"wake-staging");
  try{
   ResumableDownload.fetch("https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",zip,41205931,HASH,12000,message->progress.update(message));
   remove(staging);staging.mkdirs();progress.update("Verifying and unpacking wake pack…");long expanded=0;int count=0;
   try(ZipInputStream in=new ZipInputStream(new FileInputStream(zip))){ZipEntry entry;byte[] b=new byte[65536];while((entry=in.getNextEntry())!=null){if(++count>100)throw new IOException("Too many wake pack files.");File target=new File(staging,entry.getName());if(!target.getCanonicalPath().startsWith(staging.getCanonicalPath()+File.separator))throw new IOException("Unsafe wake pack path.");if(entry.isDirectory()){target.mkdirs();continue;}target.getParentFile().mkdirs();try(OutputStream out=new FileOutputStream(target)){int n;while((n=in.read(b))!=-1){expanded+=n;if(expanded>120000000)throw new IOException("Wake pack exceeds unpacked size limit.");out.write(b,0,n);}}}}
   File unpacked=new File(staging,"vosk-model-small-en-us-0.15");if(!new File(unpacked,"am/final.mdl").isFile()||!new File(unpacked,"graph/Gr.fst").isFile())throw new IOException("Wake pack is incomplete.");
   try(OutputStream out=new FileOutputStream(new File(unpacked,"ready.sha256"))){out.write(HASH.getBytes("US-ASCII"));}
   File destination=model(context);destination.getParentFile().mkdirs();remove(destination);if(!unpacked.renameTo(destination))throw new IOException("Could not store wake pack.");
   zip.delete();
  }finally{remove(staging);}
 }
 // Only fixed, app-private staging/model directories are passed here.
 static void remove(File f){File[] children=f.listFiles();if(children!=null)for(File child:children)remove(child);f.delete();}
}
