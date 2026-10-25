package app.sakura.mobile;
import java.io.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;

final class PhoneModelImport {
 static JSONObject importModel(InputStream input,String filename,File root)throws Exception {
  root.mkdirs();File stage=new File(root,"incoming-"+UUID.randomUUID());stage.mkdirs();
  String id=UUID.randomUUID().toString().replace("-","");
  try {
   List<String> candidates=new ArrayList<>();String lower=filename.toLowerCase(Locale.ROOT);
   if(lower.endsWith(".vrm")) {
    copy(input,new File(stage,"model.vrm"),500000000L);candidates.add("model.vrm");
   } else if(lower.endsWith(".zip")) {
    long total=0;int count=0;Set<String> names=new HashSet<>();
    try(ZipInputStream zip=new ZipInputStream(input)){ZipEntry item;byte[] buffer=new byte[65536];
     while((item=zip.getNextEntry())!=null){String name=item.getName();File target=new File(stage,name);
      if(++count>2500||name.contains("\\")||name.contains(":")||name.startsWith("/")||!names.add(name)||!target.getCanonicalPath().startsWith(stage.getCanonicalPath()+File.separator))throw new IOException("Unsafe model ZIP. Keep one complete model in the archive.");
      if(item.isDirectory()){target.mkdirs();continue;}target.getParentFile().mkdirs();
      try(OutputStream out=new FileOutputStream(target)){int n;while((n=zip.read(buffer))!=-1){total+=n;if(total>1000000000L)throw new IOException("Expanded model exceeds 1 GB.");out.write(buffer,0,n);}}
      String ext=name.toLowerCase(Locale.ROOT);if(ext.endsWith(".vrm")||ext.endsWith(".pmx")||ext.endsWith(".model3.json"))candidates.add(name);
     }
    }
   } else throw new IOException("Choose a VRM file or a ZIP containing one PMX, VRM or Live2D model and its textures.");
   if(candidates.size()!=1)throw new IOException("The ZIP must contain exactly one model entry (.vrm, .pmx or .model3.json).");
   String entry=candidates.get(0),ext=entry.toLowerCase(Locale.ROOT),format=ext.endsWith(".vrm")?"vrm":ext.endsWith(".pmx")?"pmx":"live2d";
   JSONObject model=new JSONObject().put("name",filename.replaceFirst("(?i)\\.(zip|vrm)$","")).put("format",format).put("entry",entry);
   try(Writer out=new OutputStreamWriter(new FileOutputStream(new File(stage,"sakura-mobile-model.json")),"UTF-8")){out.write(model.toString());}
   if(!stage.renameTo(new File(root,id)))throw new IOException("Not enough storage to import this model.");
   return model.put("id",id).put("url","/models/"+id+"/"+entry);
  } finally {MobileModels.remove(stage);}
 }
 static void copy(InputStream input,File target,long limit)throws Exception {
  try(OutputStream out=new FileOutputStream(target)){byte[] buffer=new byte[65536];long size=0;int n;while((n=input.read(buffer))!=-1){size+=n;if(size>limit)throw new IOException("Model exceeds 500 MB.");out.write(buffer,0,n);}}
 }
}
