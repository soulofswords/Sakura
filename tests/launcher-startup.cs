using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

static class StartupCheck {
 static readonly BindingFlags Private=BindingFlags.Instance|BindingFlags.NonPublic;
 static void Require(bool value,string message){if(!value)throw new Exception(message);}
 [STAThread] static int Main(string[] args) {
  Application.EnableVisualStyles();
  var type=Assembly.LoadFrom(args[0]).GetType("StartupDialog",true);
  var directory=Path.Combine(Path.GetTempPath(),"sakura-startup-check-"+Guid.NewGuid());
  Directory.CreateDirectory(Path.Combine(directory,"launcher"));
  File.Copy(args[1],Path.Combine(directory,"launcher","companion.ico"));
  Directory.CreateDirectory(Path.Combine(directory,"runtime"));
  // A tiny check-only executable stands in for a verified local model installation.
  File.Copy(args[2],Path.Combine(directory,"runtime","python.exe"));
  try {
   foreach(var mode in new[]{"local","vtuber","gemini"}) {
    using(var form=(Form)Activator.CreateInstance(type,Private,null,new object[]{directory},null)) {
     var keyBox=(TextBox)type.GetField("keyBox",Private).GetValue(form);
     Require(keyBox.UseSystemPasswordChar,"API key must be masked");
     Require(form.CancelButton!=null,"Escape must close the chooser");
     if(mode=="gemini") {
      type.GetMethod("SelectMode",Private).Invoke(form,new object[]{mode});
      Require(type.GetField("SelectedMode",Private).GetValue(form)==null,"Missing key must not launch Gemini");
      keyBox.Text="test-key-not-a-real-credential";
     }
     type.GetMethod("SelectMode",Private).Invoke(form,new object[]{mode});
     Require((string)type.GetField("SelectedMode",Private).GetValue(form)==mode,"Incorrect startup mode");
     Require((string)type.GetField("ApiKey",Private).GetValue(form)==(mode=="gemini"?keyBox.Text:""),"Key leaked into another mode");
    }
   }
   File.WriteAllText(Path.Combine(directory,".gemini-key.bin"),"fixture");
   using(var form=(Form)Activator.CreateInstance(type,Private,null,new object[]{directory},null)) {
    type.GetMethod("SelectMode",Private).Invoke(form,new object[]{"gemini"});
    Require((string)type.GetField("SelectedMode",Private).GetValue(form)=="gemini","Saved-key Gemini selection failed");
    Require((string)type.GetField("ApiKey",Private).GetValue(form)=="","Saved key must remain outside the UI");
   }
   Console.WriteLine("PASS: Local/VTuber/Gemini selection, missing-key validation, saved key, masked input and Escape close wiring");
   return 0;
  }finally{Directory.Delete(directory,true);}
 }
}
