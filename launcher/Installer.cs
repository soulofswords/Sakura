using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using System.Security.Cryptography;

[assembly: AssemblyTitle("Sakura Companion Setup")]
[assembly: AssemblyProduct("Sakura Companion")]
[assembly: AssemblyCompany("SoulOfSwords")]
[assembly: AssemblyCopyright("SoulOfSwords")]
[assembly: AssemblyVersion("1.1.0.0")]

sealed class Installer : Form {
 readonly TextBox destination;
 readonly ComboBox mode;
 readonly Label status;
 readonly ProgressBar progress;
 readonly Button install;
 readonly Button browse;
 readonly CheckBox launch;
 readonly CheckBox desktopShortcut;
 bool installing;
 bool completed;
 internal Installer() {
  Text="Install Sakura Companion";ClientSize=new Size(620,420);StartPosition=FormStartPosition.CenterScreen;
  BackColor=Color.FromArgb(12,15,26);ForeColor=Color.White;Font=new Font("Segoe UI",11);
  FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;MinimizeBox=false;
  Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);
  Controls.Add(new Label {Text="Welcome to Sakura",Font=new Font("Segoe UI",25,FontStyle.Bold),Location=new Point(28,24),Size=new Size(550,50)});
  Controls.Add(new Label {Text="No character, voice or AI models are bundled. Import your own later.",Location=new Point(30,83),Size=new Size(560,28)});
  Controls.Add(new Label {Text="Install location",Location=new Point(30,130),Size=new Size(540,25)});
  string defaultPath=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Sakura Companion");
  string existing=FindExisting(RegistryLocations(),new[]{defaultPath,Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"Sakura Companion"),AppDomain.CurrentDomain.BaseDirectory});
  destination=new TextBox {Text=existing??defaultPath,Location=new Point(30,160),Size=new Size(435,28)};Controls.Add(destination);
  browse=new Button {Text="Browse…",Location=new Point(479,158),Size=new Size(111,32)};Controls.Add(browse);
  browse.Click+=(s,e)=>BrowseDestination();
  Controls.Add(new Label {Text="Optional local AI (downloads after installation)",Location=new Point(30,206),Size=new Size(560,28)});
  mode=new ComboBox {Location=new Point(30,239),Size=new Size(560,30),DropDownStyle=ComboBoxStyle.DropDownList};
  mode.Items.AddRange(new object[]{"Gemini API key — skip local AI download","Qwen 2B — 8 GB RAM / 4 GB VRAM recommended","Qwen 4B — 16 GB RAM / 6–8 GB VRAM recommended"});mode.SelectedIndex=0;Controls.Add(mode);
  status=new Label {Text=InstallationStatus(destination.Text),Location=new Point(30,283),Size=new Size(560,35)};Controls.Add(status);
  destination.TextChanged+=(s,e)=>status.Text=InstallationStatus(destination.Text);
  desktopShortcut=new CheckBox {Text="Create desktop shortcut",Checked=true,Location=new Point(30,320),Size=new Size(280,27)};Controls.Add(desktopShortcut);
  launch=new CheckBox {Text="Launch after installation",Checked=true,Location=new Point(320,320),Size=new Size(270,27)};Controls.Add(launch);
  progress=new ProgressBar {Location=new Point(30,370),Size=new Size(385,20)};Controls.Add(progress);
  install=new Button {Text="Install",Location=new Point(438,364),Size=new Size(152,36)};Controls.Add(install);
  install.Click+=async(s,e)=>await RunInstall();
  FormClosing+=(s,e)=>{if(installing)e.Cancel=true;};
 }
 void BrowseDestination() {
  using(var dialog=new FolderBrowserDialog {Description="Choose the Sakura Companion installation folder",ShowNewFolderButton=true}) {
   try {
    string selected=Path.GetFullPath(destination.Text);
    while(!Directory.Exists(selected)&&Path.GetDirectoryName(selected)!=null)selected=Path.GetDirectoryName(selected);
    if(Directory.Exists(selected))dialog.SelectedPath=selected;
   }catch(ArgumentException){}catch(NotSupportedException){}catch(PathTooLongException){}
   if(dialog.ShowDialog(this)==DialogResult.OK)destination.Text=dialog.SelectedPath;
  }
 }
 void FinishInstallation() {installing=false;completed=true;Close();}
 internal static bool Existing(string directory) {
  try {
   string root=Path.GetFullPath(directory);
   return File.Exists(Path.Combine(root,".sakura-installation")) ||
    (File.Exists(Path.Combine(root,"Sakura","settings.json"))&&
     (File.Exists(Path.Combine(root,"Desktop Companion.exe"))||File.Exists(Path.Combine(root,"Sakura","app.py"))));
  }catch(ArgumentException){return false;}catch(NotSupportedException){return false;}catch(PathTooLongException){return false;}
 }
 internal static string FindExisting(IEnumerable<string> registry,IEnumerable<string> defaults) {
  foreach(var candidates in new[]{registry,defaults})foreach(string path in candidates)
   if(!string.IsNullOrWhiteSpace(path)&&Existing(path))return Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar);
  return null;
 }
 static IEnumerable<string> RegistryLocations() {
  var paths=new List<string>();
  foreach(var hive in new[]{RegistryHive.CurrentUser,RegistryHive.LocalMachine})foreach(var view in new[]{RegistryView.Registry64,RegistryView.Registry32}) {
   try {using(var root=RegistryKey.OpenBaseKey(hive,view))using(var key=root.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\SakuraCompanion"))
    if(key!=null)paths.Add(Convert.ToString(key.GetValue("InstallLocation")));}catch(System.Security.SecurityException){}catch(UnauthorizedAccessException){}
  }
  return paths;
 }
 static Dictionary<string,object> ReadConfig(string path) {
  var config=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(path));
  if(config==null)throw new ArgumentException("Configuration must be a JSON object.");
  return config;
 }
 internal static string InstallationStatus(string path) {
  if(!Existing(path))return "New installation — defaults applied";
  try {var cfg=ReadConfig(Path.Combine(path,"Sakura","settings.json"));object value;
   if(cfg.TryGetValue("preserve_configuration_on_reinstall",out value)&&value is bool&&!(bool)value)
    return "Existing installation detected — configuration reset selected (backup kept).";
  }catch(IOException){}catch(ArgumentException){}catch(UnauthorizedAccessException){}catch(InvalidOperationException){}
  return "Existing installation detected — settings preserved";
 }
 internal static string UpdatedConfig(string defaults,string existing) {
  var parser=new JavaScriptSerializer();var fresh=parser.Deserialize<Dictionary<string,object>>(defaults);
  if(fresh==null)throw new ArgumentException("Default configuration must be a JSON object.");
  if(existing==null)return parser.Serialize(fresh);
  var saved=parser.Deserialize<Dictionary<string,object>>(existing);object value;
  if(saved==null)throw new ArgumentException("Saved configuration must be a JSON object. Restore it before reinstalling.");
  bool preserve=!saved.TryGetValue("preserve_configuration_on_reinstall",out value)||!(value is bool)|| (bool)value;
  if(preserve) {
   // Older versions stored these in the browser profile. Leave absent values
   // unset so the client can migrate them instead of applying fresh defaults.
   foreach(string field in new[]{"model_quality","physics_mode","physics_boost","physics_enabled","physics_wind","pmx_texture_reference"})
    if(!saved.ContainsKey(field))fresh.Remove(field);
   foreach(var pair in saved)fresh[pair.Key]=pair.Value;
  }
  else fresh["preserve_configuration_on_reinstall"]=false;
  return parser.Serialize(fresh);
 }
 internal static void Extract(string directory,Action<int> progress=null) {
  directory=Path.GetFullPath(directory);
  Directory.CreateDirectory(directory);
  string settings=Path.Combine(directory,"Sakura","settings.json");
  string oldSettings=File.Exists(settings)?File.ReadAllText(settings):null;
  // Parse before changing binaries. Malformed config must not be silently lost.
  if(oldSettings!=null)UpdatedConfig("{}",oldSettings);
  var artwork=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
  string manifest=Path.Combine(directory,"Sakura","installed-files.tsv");
  if(File.Exists(manifest))foreach(string row in File.ReadAllLines(manifest)) {var fields=row.Split('\t');if(fields.Length==2)artwork[fields[1]]=fields[0];}
  // The payload is an allowlisted base app; never overwrite an existing user's settings.
  using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("SakuraPayload"))
  using(var zip=new ZipArchive(stream,ZipArchiveMode.Read)) {
   int done=0;
   foreach(var entry in zip.Entries) {
    string target=Path.GetFullPath(Path.Combine(directory,entry.FullName.Replace('/',Path.DirectorySeparatorChar)));
    if(!target.StartsWith(directory.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("Invalid package path.");
    // Refuse junctions/symlinks so an upgrade cannot write outside the install folder.
    for(string parent=Path.GetDirectoryName(target);parent!=null&&parent.Length>=directory.Length;parent=Path.GetDirectoryName(parent))
     if(Directory.Exists(parent)&&(File.GetAttributes(parent)&FileAttributes.ReparsePoint)!=0)throw new IOException("Choose an install folder without links or junctions.");
    if(File.Exists(target)&&(File.GetAttributes(target)&FileAttributes.ReparsePoint)!=0)throw new IOException("Install target contains a file link.");
    if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(target);continue;}
    Directory.CreateDirectory(Path.GetDirectoryName(target));
    bool keepArtwork=false;
    bool personalAsset=entry.FullName.StartsWith("Sakura/static/assets/",StringComparison.OrdinalIgnoreCase)||
     entry.FullName.StartsWith("Sakura/personality/",StringComparison.OrdinalIgnoreCase)||
     (entry.FullName.StartsWith("Sakura/launcher/",StringComparison.OrdinalIgnoreCase)&&entry.FullName.EndsWith(".ico",StringComparison.OrdinalIgnoreCase));
    if(File.Exists(target)&&personalAsset) {
     string expected;using(var sha=SHA256.Create())using(var input=File.OpenRead(target))
      keepArtwork=!artwork.TryGetValue(entry.FullName,out expected)||expected!=BitConverter.ToString(sha.ComputeHash(input)).Replace("-","").ToLowerInvariant();
    }
    if(!keepArtwork) {
     string temporary=target+".installing";
     if(entry.FullName=="Sakura/settings.json") {
      string defaults;using(var reader=new StreamReader(entry.Open()))defaults=reader.ReadToEnd();
      if(oldSettings!=null)File.WriteAllText(settings+".before-update-"+Guid.NewGuid().ToString("N")+".json",oldSettings);
      File.WriteAllText(temporary,UpdatedConfig(defaults,oldSettings));
     } else using(var input=entry.Open())using(var output=File.Create(temporary))input.CopyTo(output);
     if(File.Exists(target))File.Delete(target);File.Move(temporary,target);
    }
    if(progress!=null)progress(++done*100/zip.Entries.Count);
   }
  }
  foreach(var folder in new[]{"models/pmx","models/vrm","models/live2d","voices","audio","llm-models/blobs","llm-models/manifests"})Directory.CreateDirectory(Path.Combine(directory,"Sakura",folder));
  File.WriteAllText(Path.Combine(directory,".sakura-installation"),"Sakura Companion installation v1");
 }
 static void Shortcut(string path,string target,string working) {
  Type type=Type.GetTypeFromProgID("WScript.Shell");object shell=Activator.CreateInstance(type);
  object link=type.InvokeMember("CreateShortcut",BindingFlags.InvokeMethod,null,shell,new object[]{path});
  Type linkType=link.GetType();
  linkType.InvokeMember("TargetPath",BindingFlags.SetProperty,null,link,new object[]{target});
  linkType.InvokeMember("WorkingDirectory",BindingFlags.SetProperty,null,link,new object[]{working});
  linkType.InvokeMember("IconLocation",BindingFlags.SetProperty,null,link,new object[]{target+",0"});
  linkType.InvokeMember("Save",BindingFlags.InvokeMethod,null,link,null);
  System.Runtime.InteropServices.Marshal.FinalReleaseComObject(link);System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
 }
 async Task RunInstall() {
  if(completed){Close();return;}
  string target;try{target=Path.GetFullPath(destination.Text);}catch(Exception error){status.Text=error.Message;return;}
  installing=true;install.Enabled=false;mode.Enabled=false;destination.Enabled=false;browse.Enabled=false;launch.Enabled=false;desktopShortcut.Enabled=false;
  int local=mode.SelectedIndex;
  string resultStatus=InstallationStatus(target);
  try {
   status.Text="Installing Sakura. Please leave this window open…";
   await Task.Run(()=>Extract(target,value=>BeginInvoke((Action)(()=>progress.Value=value))));
   string exe=Path.Combine(target,"Desktop Companion.exe");
   if(desktopShortcut.Checked)Shortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"Sakura Companion.lnk"),exe,target);
   string menu=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.StartMenu),"Programs","Sakura Companion");Directory.CreateDirectory(menu);
   Shortcut(Path.Combine(menu,"Sakura Companion.lnk"),exe,target);
   using(var key=Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\SakuraCompanion")) {
    key.SetValue("DisplayName","Sakura Companion");key.SetValue("DisplayVersion","1.1.0");key.SetValue("InstallLocation",target);
    key.SetValue("Publisher","SoulOfSwords");
    key.SetValue("DisplayIcon",exe);key.SetValue("UninstallString","\""+Path.Combine(target,"Sakura","Uninstall.exe")+"\"");
   }
   status.Text=resultStatus;
   if(local>0)Process.Start(new ProcessStartInfo(exe,"--setup-local "+(local==1?"2b":"4b")){WorkingDirectory=target});
   else if(launch.Checked)Process.Start(new ProcessStartInfo(exe){WorkingDirectory=target});
   FinishInstallation();
  }catch(Exception error){status.Text="Installation failed: "+error.Message;install.Enabled=true;mode.Enabled=true;destination.Enabled=true;browse.Enabled=true;launch.Enabled=true;desktopShortcut.Enabled=true;}
  finally{installing=false;}
 }
 [STAThread] static int Main(string[] args) {
  if(args.Length==2&&args[0]=="--test-install"){try{Extract(args[1]);return 0;}catch(Exception e){Console.Error.WriteLine(e);return 1;}}
  Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Installer());return 0;
 }
}
