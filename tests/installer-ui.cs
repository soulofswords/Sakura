using System;
using System.Reflection;
using System.Windows.Forms;
static class InstallerUiCheck {
 static readonly BindingFlags Private=BindingFlags.Instance|BindingFlags.NonPublic;
 static void Require(bool ok,string message){if(!ok)throw new Exception(message);}
 [STAThread] static int Main(string[] args) {
  Application.EnableVisualStyles();
  var type=Assembly.LoadFrom(args[0]).GetType("Installer",true);
  using(var form=(Form)Activator.CreateInstance(type,Private,null,new object[0],null)) {
   var cuda=(ComboBox)type.GetField("cudaOptions",Private).GetValue(form);
   var cudaStatus=(Label)type.GetField("cudaStatus",Private).GetValue(form);
   Require(cuda.Items.Count==2&&cuda.SelectedIndex==0,"CUDA must be optional and skipped by default");
   Require(cuda.Items[1].ToString().Contains("670 MB"),"CUDA download size is missing");
   cuda.SelectedIndex=1;Require(cuda.SelectedIndex==1,"CUDA installation cannot be selected");
   Require(form.ClientRectangle.Contains(cuda.Bounds)&&cuda.Bottom<=cudaStatus.Top,"CUDA option outside installer or overlapping detection status");
   var destination=(TextBox)type.GetField("destination",Private).GetValue(form);
   var browse=(Button)type.GetField("browse",Private).GetValue(form);
   var launch=(CheckBox)type.GetField("launch",Private).GetValue(form);
   var shortcut=(CheckBox)type.GetField("desktopShortcut",Private).GetValue(form);
   Require(shortcut.Checked&&shortcut.Right<=launch.Left,"Desktop shortcut checkbox missing or overlapping");
   shortcut.Checked=false;Require(!shortcut.Checked,"Shortcut cannot be disabled");
   Require(browse.Enabled&&browse.Text.StartsWith("Browse"),"Browse button missing");
   Require(destination.Right<browse.Left,"Browse button overlaps path field");
   Require(form.ClientRectangle.Contains(browse.Bounds)&&form.ClientRectangle.Contains(launch.Bounds),"New controls outside installer");
   Require(launch.Checked,"Default launch choice missing");
   launch.Checked=false;Require(!launch.Checked,"Launch cannot be disabled");
   type.GetField("installing",Private).SetValue(form,true);
   var closing=new FormClosingEventArgs(CloseReason.UserClosing,false);
   typeof(Form).GetMethod("OnFormClosing",Private).Invoke(form,new object[]{closing});
   Require(closing.Cancel,"Installer can close during extraction");
   type.GetMethod("FinishInstallation",Private).Invoke(form,new object[0]);
   Require(!(bool)type.GetField("installing",Private).GetValue(form),"Success leaves close blocked");
   Require(form.IsDisposed,"Successful installation does not auto-close");
  }
  Console.WriteLine("PASS: Browse control, layout, optional launch, extraction close guard and automatic successful close");
  return 0;
 }
}
