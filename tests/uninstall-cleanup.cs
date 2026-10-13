using System;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
class CheckUninstall {
 static void Assert(bool ok,string message){if(!ok)throw new Exception(message);}
 static string Fixture(string baseDir,string name) {
  string root=Path.Combine(baseDir,name);Directory.CreateDirectory(Path.Combine(root,"Sakura","models","pmx"));
  File.WriteAllText(Path.Combine(root,".sakura-installation"),"Sakura Companion installation v1");
  string app=Path.Combine(root,"Sakura","app.py");File.WriteAllText(app,"installed original");
  string hash;using(var sha=SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(app))).Replace("-","").ToLowerInvariant();
  File.WriteAllText(Path.Combine(root,"Sakura","installed-files.tsv"),hash+"\tSakura/app.py");
  File.WriteAllText(Path.Combine(root,"Sakura","models","pmx","mine.pmx"),"user data");
  File.WriteAllText(Path.Combine(root,"Sakura","settings.json"),"private settings");
  return root;
 }
 static void Main(string[] args) {
  string dir=Path.Combine(Path.GetTempPath(),"sakura-uninstall-test-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(dir);
  var method=Assembly.LoadFrom(Path.GetFullPath(args[0])).GetType("Uninstall").GetMethod("RemoveInstallation",BindingFlags.Public|BindingFlags.Static);
  try {
   string root=Fixture(dir,"preserve"),backup=(string)method.Invoke(null,new object[]{root,true});
   Assert(!Directory.Exists(root),"Install root still exists");Assert(File.ReadAllText(Path.Combine(backup,"Sakura","models","pmx","mine.pmx"))=="user data","User model not backed up");Assert(!File.Exists(Path.Combine(backup,"Sakura","app.py")),"Original program should not be backed up");
   root=Fixture(dir,"remove");Assert(method.Invoke(null,new object[]{root,false})==null,"Unexpected backup");Assert(!Directory.Exists(root),"Remove all left root");
   root=Fixture(dir,"locked");using(var locked=new FileStream(Path.Combine(root,"Sakura","app.py"),FileMode.Open,FileAccess.Read,FileShare.None)) {
    bool rejected=false;try{method.Invoke(null,new object[]{root,false});}catch(TargetInvocationException){rejected=true;}Assert(rejected&&File.Exists(Path.Combine(root,"Sakura","models","pmx","mine.pmx")),"Locked uninstall partially deleted user files");
   }
   root=Fixture(dir,"unmarked");File.Delete(Path.Combine(root,".sakura-installation"));bool refused=false;try{method.Invoke(null,new object[]{root,false});}catch(TargetInvocationException){refused=true;}Assert(refused&&File.Exists(Path.Combine(root,"Sakura","app.py")),"Unmarked folder deleted");
   root=Fixture(dir,"modified");File.WriteAllText(Path.Combine(root,"Sakura","app.py"),"user modification");backup=(string)method.Invoke(null,new object[]{root,true});Assert(File.ReadAllText(Path.Combine(backup,"Sakura","app.py"))=="user modification","Modified code not kept");
   Console.WriteLine("PASS: complete root removal, separate user backup, remove-all, modified files, locked app and unmarked-folder refusal");
  }finally{Directory.Delete(dir,true);}
 }
}