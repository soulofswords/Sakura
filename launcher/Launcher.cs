using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;
using System.Threading;
using System.Drawing;
using System.Runtime.InteropServices;
[assembly: AssemblyTitle("Sakura Companion")]
[assembly: AssemblyDescription("Sakura Companion")]
[assembly: AssemblyProduct("Sakura Companion")]
[assembly: AssemblyCompany("SoulOfSwords")]
[assembly: AssemblyCopyright("SoulOfSwords")]
[assembly: AssemblyVersion("1.0.0.0")]
static class Launcher {
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern IntPtr FindWindow(string className,string title);
 [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);
 [DllImport("user32.dll")] static extern bool ShowWindowAsync(IntPtr window,int command);
 [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window,out uint processId);
 [DllImport("user32.dll")] static extern bool AllowSetForegroundWindow(uint processId);
 static bool FocusExisting(string title) {
  IntPtr handle=FindWindow(null,title);
  if(handle==IntPtr.Zero)handle=FindWindow(null,title+" — Choose startup mode");
  if(handle==IntPtr.Zero)return false;
  uint owner;GetWindowThreadProcessId(handle,out owner);AllowSetForegroundWindow(owner);
  if(IsIconic(handle))ShowWindowAsync(handle,9); // Restore only a genuinely minimized window.
  SetForegroundWindow(handle);return true;
 }
 static void FocusStartedWindow(Process process,string title) {
  uint id=(uint)process.Id;
  AllowSetForegroundWindow(id);
  var focus=new Thread(()=>{
   for(int attempt=0;attempt<180;attempt++) {
    try{if(process.HasExited)return;}catch(InvalidOperationException){return;}
    IntPtr handle=FindWindow(null,title);uint owner=0;
    if(handle!=IntPtr.Zero)GetWindowThreadProcessId(handle,out owner);
    if(owner==id){if(IsIconic(handle))ShowWindowAsync(handle,9);SetForegroundWindow(handle);return;}
    Thread.Sleep(250);
   }
  });focus.IsBackground=true;focus.Start();
 }
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern IntPtr LoadLibraryEx(string file,IntPtr reserved,uint flags);
 [DllImport("kernel32.dll")] static extern IntPtr FindResource(IntPtr module,IntPtr name,IntPtr type);
 [DllImport("kernel32.dll")] static extern IntPtr LoadResource(IntPtr module,IntPtr resource);
 [DllImport("kernel32.dll")] static extern uint SizeofResource(IntPtr module,IntPtr resource);
 [DllImport("kernel32.dll")] static extern IntPtr LockResource(IntPtr resource);
 [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr module);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr BeginUpdateResource(string file,bool deleteExisting);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool UpdateResource(IntPtr update,IntPtr type,IntPtr name,ushort language,byte[] data,uint size);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool EndUpdateResource(IntPtr update,bool discard);
 static string BrandedPython(string python) {
  // OBS identifies windows by their owning executable as well as the title.
  // A separate interpreter copy gives it Sakura's name and version metadata.
  string launcher=Assembly.GetExecutingAssembly().Location;
  string output=Path.Combine(Path.GetDirectoryName(python),"Sakura Companion.exe");
  if(File.Exists(output)&&File.GetLastWriteTimeUtc(output)>=File.GetLastWriteTimeUtc(python)&&File.GetLastWriteTimeUtc(output)>=File.GetLastWriteTimeUtc(launcher))return output;
  string temporary=output+".building-"+Guid.NewGuid().ToString("N");
  try {
   File.Copy(python,temporary);
   IntPtr module=LoadLibraryEx(launcher,IntPtr.Zero,2);if(module==IntPtr.Zero)throw new IOException("Could not read Sakura branding.");
   byte[] bytes;
   try {
    IntPtr resource=FindResource(module,(IntPtr)1,(IntPtr)16);uint length=SizeofResource(module,resource);
    if(length==0)throw new IOException("Sakura version metadata is missing.");
    bytes=new byte[length];Marshal.Copy(LockResource(LoadResource(module,resource)),bytes,0,(int)length);
   } finally {FreeLibrary(module);}
   IntPtr update=BeginUpdateResource(temporary,false);if(update==IntPtr.Zero)throw new IOException("Could not brand the Sakura runtime.");
   bool written=false;
   try{written=UpdateResource(update,(IntPtr)16,(IntPtr)1,0,bytes,(uint)bytes.Length);}
   finally{if(!EndUpdateResource(update,!written))written=false;}
   if(!written)throw new IOException("Could not save Sakura runtime metadata.");
   File.Copy(temporary,output,true);File.SetLastWriteTimeUtc(output,DateTime.UtcNow);
   return output;
  } catch(Exception error) {Debug.WriteLine("Sakura runtime branding: "+error.Message);return python;}
  finally{if(File.Exists(temporary))File.Delete(temporary);}
 }
 static string ChooseMode(string project, out string key) {
  using(var dialog=new StartupDialog(project)) {
   dialog.ShowDialog();
   key=dialog.ApiKey; return dialog.SelectedMode;
  }
 }
 [STAThread] static void Main(string[] args) {
  Application.EnableVisualStyles();
  Application.SetCompatibleTextRenderingDefault(false);
  string root=AppDomain.CurrentDomain.BaseDirectory;
  // Keep the single user-facing launcher in the project root. Everything else
  // lives in the Sakura folder so the install stays tidy.
  string project=Path.Combine(root,"Sakura");
  string script="desktop.py";string title="Desktop Companion";
  // Build checks validate this installation without taking the interactive
  // launcher's mutex or showing a dialog over a running camera session.
  if(args.Length==1&&args[0]=="--check") {
   string checkPython=LocalModelDialog.Python(project);
   if(!File.Exists(checkPython)||!File.Exists(Path.Combine(project,script)))Environment.ExitCode=1;
   return;
  }
  bool created; using(var mutex=new Mutex(true,"Local\\SakuraLauncher_"+title.Replace(" ","_"),out created)) {
   if(!created && title!="Sakura VTuber"){
    if(!FocusExisting(title))MessageBox.Show(title+" is starting. Please wait a moment, then open it again to bring it forward.",title);
    return;
   }
   try {
    string python=LocalModelDialog.Python(project);
    if(!File.Exists(python)||!File.Exists(Path.Combine(project,script))) throw new IOException("Keep this launcher beside the Sakura folder that contains its venv and source files.");
    if(args.Length>0&&args[0]=="--setup-local") {
     using(var setup=new LocalModelDialog(project,args.Length>1?args[1]:null))setup.ShowDialog();return;
    }
    string key; string mode=ChooseMode(project,out key); if(mode==null)return;
    python=BrandedPython(python);
    // Start from Sakura's working directory just like a direct successful run.
    // The native window receives Sakura's own AppUserModelID and icon in
    // desktop.py, so the interpreter remains hidden behind the branded UI.
    var start=new ProcessStartInfo(python,"-u \""+script+"\"");
    start.WorkingDirectory=project;start.UseShellExecute=false;start.CreateNoWindow=true;
    start.RedirectStandardOutput=true;start.RedirectStandardError=true;
    start.StandardOutputEncoding=Encoding.UTF8;start.StandardErrorEncoding=Encoding.UTF8;
    start.EnvironmentVariables["PYTHONUTF8"]="1";start.EnvironmentVariables["PYTHONUNBUFFERED"]="1";
    start.EnvironmentVariables["SAKURA_DESKTOP"]=script=="desktop.py"?"1":"0";
    start.EnvironmentVariables["SAKURA_UPLOAD_UI"]="1";
    start.EnvironmentVariables["SAKURA_START_MODE"]=mode;
    if(key.Length>0) start.EnvironmentVariables["SAKURA_START_GEMINI_KEY"]=key;
    string logs=Path.Combine(project,"logs");Directory.CreateDirectory(logs);
    using(var log=new StreamWriter(Path.Combine(logs,title.Replace(" ","-").ToLower()+(title=="Sakura VTuber"?"-"+Process.GetCurrentProcess().Id:"")+"-launch.log"),true,Encoding.UTF8)) {
     log.AutoFlush=true;object sync=new object();
     using(var process=new Process()) {
      process.StartInfo=start;
      DataReceivedEventHandler output=(sender,e)=>{if(e.Data!=null)lock(sync)log.WriteLine(e.Data);};
      process.OutputDataReceived+=output;process.ErrorDataReceived+=output;
      process.Start();FocusStartedWindow(process,title);process.BeginOutputReadLine();process.BeginErrorReadLine();process.WaitForExit();
      if(process.ExitCode!=0) MessageBox.Show(title+" stopped with an error. Check the launch log in Sakura\\logs.",title);
     }
    }
   }catch(Exception error){MessageBox.Show(error.Message,title,MessageBoxButtons.OK,MessageBoxIcon.Error);}
  }
 }
}
