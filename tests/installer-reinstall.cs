using System;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
using System.Collections.Generic;
static class ReinstallCheck {
 static Type installer;
 static object Call(string name,params object[] args){return installer.GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,args);}
 static void Require(bool ok,string message){if(!ok)throw new Exception(message);}
 static int Main(string[] args) {
  installer=Assembly.LoadFrom(args[0]).GetType("Installer",true);
  string root=Path.Combine(Path.GetTempPath(),"sakura-reinstall-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
  try {
   string registered=Path.Combine(root,"registered"),legacy=Path.Combine(root,"legacy"),missing=Path.Combine(root,"missing");
   Directory.CreateDirectory(registered);File.WriteAllText(Path.Combine(registered,".sakura-installation"),"Sakura Companion installation v1");
   Directory.CreateDirectory(Path.Combine(legacy,"Sakura"));File.WriteAllText(Path.Combine(legacy,"Sakura","settings.json"),"{}");File.WriteAllText(Path.Combine(legacy,"Sakura","app.py"),"fixture");
   Require((string)Call("FindExisting",new[]{missing,registered},new[]{legacy})==registered,"Registry install must take precedence");
   Require((string)Call("FindExisting",new[]{missing},new[]{legacy})==legacy,"Legacy configuration detection failed");
   Require(Call("FindExisting",new[]{missing},new[]{missing})==null,"Missing installation detected");
   Require((string)Call("InstallationStatus",missing)=="New installation — defaults applied","Fresh status incorrect");
   Require((string)Call("InstallationStatus",legacy)=="Existing installation detected — settings preserved","Upgrade status incorrect");
   var parser=new JavaScriptSerializer();string defaults="{\"preserve_configuration_on_reinstall\":true,\"physics_boost\":0,\"new_option\":true}";
   var merged=parser.Deserialize<Dictionary<string,object>>((string)Call("UpdatedConfig",defaults,"{\"physics_boost\":85,\"models_folder\":\"custom\",\"pmx_texture_reference\":true,\"unknown\":12}"));
   Require((int)merged["physics_boost"]==85&&(string)merged["models_folder"]=="custom"&&(bool)merged["pmx_texture_reference"],"Saved preferences lost");
   Require((bool)merged["new_option"]&&(int)merged["unknown"]==12&&(bool)merged["preserve_configuration_on_reinstall"],"Merge/default preservation failed");
   var legacyConfig=parser.Deserialize<Dictionary<string,object>>((string)Call("UpdatedConfig",defaults,"{}"));
   Require(!legacyConfig.ContainsKey("physics_boost"),"New defaults would erase browser-only physics preferences before migration");
   var reset=parser.Deserialize<Dictionary<string,object>>((string)Call("UpdatedConfig",defaults,"{\"preserve_configuration_on_reinstall\":false,\"physics_boost\":85}"));
   Require((int)reset["physics_boost"]==0&&!(bool)reset["preserve_configuration_on_reinstall"],"Explicit reset ignored");
   foreach(string bad in new[]{"null","broken JSON"}) {
    bool rejected=false;try{Call("UpdatedConfig",defaults,bad);}catch(TargetInvocationException){rejected=true;}
    Require(rejected,"Malformed configuration silently overwritten");
   }
   Console.WriteLine("PASS: existing-path detection, exact statuses, settings merge, reset and malformed-config protection");return 0;
  }finally{Directory.Delete(root,true);}
 }
}
