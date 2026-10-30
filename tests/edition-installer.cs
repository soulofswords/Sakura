using System;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Collections.Generic;
static class EditionInstallerCheck {
 static void Require(bool ok,string why){if(!ok)throw new Exception(why);}
 static IEnumerable<string> Labels(Control control){yield return control.Text;var combo=control as ComboBox;if(combo!=null)foreach(object item in combo.Items)yield return item.ToString();foreach(Control child in control.Controls)foreach(string label in Labels(child))yield return label;}
 [STAThread] static int Main(string[] args){
  var type=Assembly.LoadFrom(args[0]).GetType("Installer",true);string display=args[2]=="vtuber"?"Sakura VTuber":"Sakura Companion";
  using(var form=(Form)Activator.CreateInstance(type,BindingFlags.Instance|BindingFlags.NonPublic,null,new object[0],null)){
   Require(form.Text=="Install "+display,"Wrong installer title");
   if(args[2]=="vtuber")foreach(string label in Labels(form))Require(!Regex.IsMatch(label,@"\b(AI|LLM|Gemini|Qwen|Ollama|Companion)\b",RegexOptions.IgnoreCase),"Unexpected tracking installer label: "+label);
  }
  var extract=type.GetMethod("Extract",BindingFlags.Static|BindingFlags.NonPublic);
  extract.Invoke(null,new object[]{args[1],null});
  string appRoot=Path.Combine(args[1],"Sakura");
  Require(Directory.GetFiles(appRoot,"sakura_core*.pyd").Length==1,"Protected native core missing");
  Require(!File.Exists(Path.Combine(appRoot,"app.py"))&&!File.Exists(Path.Combine(appRoot,"llm.py")),"Readable application Python leaked");
  foreach(string asset in Directory.GetFiles(Path.Combine(appRoot,"static"),"*",SearchOption.AllDirectories))
   Require(!Regex.IsMatch(Path.GetFileName(asset),@"(?i)(\.(bak|backup|orig|rej|tmp|swp|swo|map)|~)$|\.before-"),"Backup/debug asset leaked: "+asset);
  // Protected JavaScript rewrites member access into string form and hoists a seeded
  // sample of those strings into its encoded array, so an implementation name such as
  // _hitModelPixelAt can legitimately vanish from the installed file. Only markers that
  // survive protection by construction are checked here; release-protection.py asserts
  // the implementation itself on the readable source before obfuscation.
  string installedViewer=File.ReadAllText(Path.Combine(appRoot,"static","js","model-viewer.js"));
  Require(installedViewer.Contains("_0x")&&installedViewer.Contains("SmartTgaLoader"),"Installed renderer is unprotected or is not this release first-party module");
  // Renderer cache-busting belongs to the module import in app.js, not the
  // HTML shell.  Keep the installer smoke test aligned with the browser's
  // actual load path so it catches a stale packaged module without rejecting
  // a valid release.
  Require(File.ReadAllText(Path.Combine(appRoot,"static","js","app.js")).Contains("cursor-gpu6"),"Stale renderer cache version");
  Require(File.Exists(Path.Combine(args[1],display+".exe")),"Branded launcher missing");
  Require(File.Exists(Path.Combine(args[1],"Sakura","tools","pmx-editor","PmxEditor.exe")),"PMX Editor integration missing");
  Require(Directory.Exists(Path.Combine(args[1],"Sakura","tools","pmx-editor","Lib")),"PMX Editor libraries missing");
  Require(File.ReadAllText(Path.Combine(args[1],".sakura-installation"))==display+" installation v1","Wrong installation marker");
  var parser=new JavaScriptSerializer();string settings=Path.Combine(args[1],"Sakura","settings.json");var cfg=parser.Deserialize<Dictionary<string,object>>(File.ReadAllText(settings));cfg["model_quality"]="high";cfg["custom_test_setting"]="kept";File.WriteAllText(settings,parser.Serialize(cfg));
  var artwork=Path.Combine(args[1],"Sakura","models","pmx","personal.txt");Directory.CreateDirectory(Path.GetDirectoryName(artwork));File.WriteAllText(artwork,"user artwork");
  extract.Invoke(null,new object[]{args[1],null});cfg=parser.Deserialize<Dictionary<string,object>>(File.ReadAllText(settings));Require((string)cfg["custom_test_setting"]=="kept"&&File.ReadAllText(artwork)=="user artwork","Update lost settings or artwork");
  File.Delete(artwork);
  string marker=Path.Combine(args[1],".sakura-installation");File.WriteAllText(marker,"Other product installation v1");bool blocked=false;try{extract.Invoke(null,new object[]{args[1],null});}catch(TargetInvocationException){blocked=true;}Require(blocked,"Cross-product overwrite allowed");File.WriteAllText(marker,display+" installation v1");
  Console.WriteLine("PASS: "+display+" UI, isolated marker, launcher, upgrade preservation and cross-product overwrite refusal");return 0;
 }
}
