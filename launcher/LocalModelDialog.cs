using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.Collections.Generic;
using System.Drawing.Drawing2D;

// Native disabled radio/button text can become black on a dark Windows theme.
// Keep the native selection/keyboard behavior, but draw readable state colours.
sealed class LocalModelChoice : RadioButton {
 internal LocalModelChoice() {
  SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);
  Font=new Font("Segoe UI",11,FontStyle.Bold);
 }
 protected override void OnPaint(PaintEventArgs e) {
  e.Graphics.Clear(BackColor);e.Graphics.SmoothingMode=SmoothingMode.AntiAlias;
  Color accent=Checked?Color.FromArgb(104,235,221):Color.FromArgb(180,194,215);
  var circle=new Rectangle(4,(Height-18)/2,18,18);
  using(var pen=new Pen(accent,2))e.Graphics.DrawEllipse(pen,circle);
  if(Checked)using(var brush=new SolidBrush(accent))e.Graphics.FillEllipse(brush,circle.X+4,circle.Y+4,10,10);
  TextRenderer.DrawText(e.Graphics,Text,Font,new Rectangle(31,0,Width-34,Height),
   Enabled?Color.FromArgb(241,248,255):Color.FromArgb(200,216,232),
   TextFormatFlags.Left|TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis);
  if(Focused&&ShowFocusCues)ControlPaint.DrawFocusRectangle(e.Graphics,new Rectangle(28,2,Width-31,Height-4),accent,BackColor);
 }
}
sealed class LocalModelAction : Button {
 internal LocalModelAction() {
  SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);
  FlatStyle=FlatStyle.Flat;Font=new Font("Segoe UI",10,FontStyle.Bold);
 }
 protected override void OnPaint(PaintEventArgs e) {
  e.Graphics.Clear(Enabled?Color.FromArgb(27,57,72):Color.FromArgb(31,39,54));
  using(var pen=new Pen(Enabled?Color.FromArgb(104,235,221):Color.FromArgb(112,133,153)))e.Graphics.DrawRectangle(pen,0,0,Width-1,Height-1);
  TextRenderer.DrawText(e.Graphics,Text,Font,ClientRectangle,
   Enabled?Color.White:Color.FromArgb(200,216,232),TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis);
  if(Focused&&ShowFocusCues)ControlPaint.DrawFocusRectangle(e.Graphics,new Rectangle(4,4,Width-8,Height-8));
 }
}

sealed class LocalModelDialog : Form {
 readonly string project;
 Process worker;
 readonly RadioButton small, large;
 readonly Button download;
 readonly Label status;
 readonly ProgressBar progress;
 internal static string Python(string project) {
  string portable=Path.Combine(project,"runtime","python.exe");
  return File.Exists(portable)?portable:Path.Combine(project,"venv","Scripts","python.exe");
 }
 internal static bool Installed(string project) {
  var info=new ProcessStartInfo(Python(project),"-u local_model_setup.py --check") {
   WorkingDirectory=project,UseShellExecute=false,CreateNoWindow=true};
  using(var child=Process.Start(info)) {
   if(!child.WaitForExit(15000)){child.Kill();return false;} return child.ExitCode==0;
  }
 }
 internal LocalModelDialog(string project,string choice=null) {
  this.project=project; Text="Sakura — Optional local AI"; ClientSize=new Size(570,390);
  BackColor=Color.FromArgb(12,15,26);ForeColor=Color.White;Font=new Font("Segoe UI",10);
  StartPosition=FormStartPosition.CenterScreen;FormBorderStyle=FormBorderStyle.FixedDialog;
  MaximizeBox=false;MinimizeBox=false;Icon=new Icon(Path.Combine(project,"launcher","companion.ico"));
  Controls.Add(new Label {Text="Choose your local companion",Location=new Point(24,24),Size=new Size(520,35),Font=new Font("Segoe UI",20,FontStyle.Bold)});
  small=new LocalModelChoice {Text="Qwen 2B · Recommended for laptops",Checked=choice!="4b",Location=new Point(28,84),Size=new Size(510,30)};
  large=new LocalModelChoice {Text="Qwen 4B · Higher quality",Checked=choice=="4b",Location=new Point(28,165),Size=new Size(510,30)};
  Controls.Add(small);Controls.Add(large);
  Controls.Add(new Label {Text="Recommended: 8 GB RAM + 4 GB VRAM. CPU fallback is slower.\nApple Silicon: 8 GB unified memory minimum; 16 GB preferred.",Location=new Point(48,119),Size=new Size(490,44),ForeColor=Color.LightGray});
  Controls.Add(new Label {Text="Recommended: 16 GB RAM + 6–8 GB VRAM, or 16 GB Apple unified\nmemory. Allow 10 GB free disk. Downloads require internet.",Location=new Point(48,202),Size=new Size(490,44),ForeColor=Color.LightGray});
  status=new Label {Text="Nothing is downloaded until you select Download. Allow 8 GB free for 2B.",Location=new Point(28,256),Size=new Size(510,44)};Controls.Add(status);
  progress=new ProgressBar {Location=new Point(28,305),Size=new Size(510,12),Style=ProgressBarStyle.Marquee};Controls.Add(progress);progress.Visible=false;
  download=new LocalModelAction {Text="Download and use local AI",Location=new Point(28,335),Size=new Size(305,34)};
  download.Click+=(s,e)=>StartDownload();Controls.Add(download);
  var cancel=new LocalModelAction {Text="Cancel",Location=new Point(353,335),Size=new Size(185,34)};
  cancel.Click+=(s,e)=>Close();Controls.Add(cancel);
  FormClosing+=(s,e)=>{if(worker!=null&&!worker.HasExited)worker.Kill();};
 }
 void StartDownload() {
  download.Enabled=false;small.Enabled=false;large.Enabled=false;progress.Visible=true;
  var info=new ProcessStartInfo(Python(project),"-u local_model_setup.py --install "+(large.Checked?"4b":"2b")) {
   WorkingDirectory=project,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
  info.EnvironmentVariables["PYTHONUTF8"]="1";
  worker=new Process {StartInfo=info,EnableRaisingEvents=true};
  DataReceivedEventHandler output=(s,e)=>{if(e.Data!=null&&!IsDisposed&&IsHandleCreated)BeginInvoke((Action)(()=>{
   try {
    var item=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(e.Data);
    status.Text=Convert.ToString(item["message"]);
    if(item.ContainsKey("percent")&&item["percent"]!=null){progress.Style=ProgressBarStyle.Continuous;progress.Value=Math.Max(0,Math.Min(100,Convert.ToInt32(item["percent"])));}
    else progress.Style=ProgressBarStyle.Marquee;
   }catch{status.Text=e.Data;}
  }));};
  worker.OutputDataReceived+=output;worker.ErrorDataReceived+=output;
  worker.Exited+=(s,e)=>{if(!IsDisposed&&IsHandleCreated)BeginInvoke((Action)(()=>{
   if(worker.ExitCode==0){DialogResult=DialogResult.OK;Close();}
   else {progress.Visible=false;download.Enabled=true;small.Enabled=true;large.Enabled=true;status.Text="Download failed or was cancelled. Retry to resume. "+status.Text;}
  }));};
  try {worker.Start();worker.BeginOutputReadLine();worker.BeginErrorReadLine();}
  catch(Exception error){worker=null;status.Text=error.Message;download.Enabled=true;small.Enabled=true;large.Enabled=true;progress.Visible=false;}
 }
}
