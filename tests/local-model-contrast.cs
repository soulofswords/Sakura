using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
static class LocalModelContrastCheck {
 static readonly BindingFlags Private=BindingFlags.Instance|BindingFlags.NonPublic;
 static void CheckText(Control control,int left) {
  using(var bitmap=new Bitmap(control.Width,control.Height)) {
   control.DrawToBitmap(bitmap,control.ClientRectangle);
   int light=0;
   for(int y=4;y<bitmap.Height-4;y++)for(int x=left;x<bitmap.Width-8;x++) {
    var pixel=bitmap.GetPixel(x,y);
    if(pixel.R>160&&pixel.G>160&&pixel.B>160)light++;
   }
   if(light<60)throw new Exception("Text is not readable: "+control.Text+", enabled="+control.Enabled);
  }
 }
 [STAThread] static int Main(string[] args) {
  Application.EnableVisualStyles();
  var folder=Path.Combine(Path.GetTempPath(),"sakura-local-contrast-"+Guid.NewGuid().ToString("N"));
  Directory.CreateDirectory(Path.Combine(folder,"launcher"));File.Copy(args[1],Path.Combine(folder,"launcher","companion.ico"));
  try {
   var type=Assembly.LoadFrom(args[0]).GetType("LocalModelDialog",true);
   using(var form=(Form)Activator.CreateInstance(type,Private,null,new object[]{folder,"2b"},null)) {
    foreach(string name in new[]{"small","large","download"}) {
     var control=(Control)type.GetField(name,Private).GetValue(form);
     CheckText(control,name=="download"?8:31);
     control.Enabled=false;CheckText(control,name=="download"?8:31);
     control.Enabled=true;
    }
    var small=(RadioButton)type.GetField("small",Private).GetValue(form);
    var large=(RadioButton)type.GetField("large",Private).GetValue(form);
    if(!small.Checked||large.Checked)throw new Exception("Default selection changed");
    large.Checked=true;if(small.Checked||!large.Checked)throw new Exception("Exclusive selection broken");
   }
   Console.WriteLine("PASS: Qwen labels and download button render light text in enabled/disabled states; native exclusive selection retained");return 0;
  }finally{Directory.Delete(folder,true);}
 }
}
