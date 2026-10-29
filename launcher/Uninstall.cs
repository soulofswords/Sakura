using System;
using System.IO;
using System.Collections.Generic;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;
[assembly: System.Reflection.AssemblyCompany("SoulOfSwords")]
[assembly: System.Reflection.AssemblyProduct("Sakura Companion")]
static class Uninstall {
 const string Marker="Sakura Companion installation v1";
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool MoveFileEx(string existing,string replacement,int flags);
 static void RemoveOwnedIntegrations(string root,string project) {
  const string run=@"Software\Microsoft\Windows\CurrentVersion\Run";
  using(var key=Registry.CurrentUser.OpenSubKey(run,true)) {
   string value=key==null?null:key.GetValue("Sakura Companion") as string;
   string launcher="\""+Path.Combine(root,"Sakura Companion.exe")+"\"";
   if(value!=null&&(value.Equals(launcher,StringComparison.OrdinalIgnoreCase)||value.StartsWith(launcher+" ",StringComparison.OrdinalIgnoreCase))) {
    key.DeleteValue("Sakura Companion",false);
    using(var approved=Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",true))
     if(approved!=null)approved.DeleteValue("Sakura Companion",false);
   }
  }
  string desired=Path.Combine(project,@"native\sakura-camera\bin\x64\sakura-camera64.dll");
  using(var key=Registry.ClassesRoot.OpenSubKey(@"CLSID\{5F4A34D7-C3B9-4E6D-9A12-8A4D3C6E7201}\InprocServer32")) {
   string registered=key==null?null:key.GetValue("") as string;
   if(registered!=null&&Path.GetFullPath(registered).Equals(Path.GetFullPath(desired),StringComparison.OrdinalIgnoreCase)&&File.Exists(desired)) {
    var info=new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),"regsvr32.exe"),"/s /u \""+desired+"\"");
    info.UseShellExecute=true;info.Verb="runas";info.WindowStyle=ProcessWindowStyle.Hidden;
    using(var process=Process.Start(info)) {
     if(!process.WaitForExit(30000)||process.ExitCode!=0)throw new IOException("Close video apps and approve camera removal before uninstalling Sakura.");
    }
   }
  }
 }
 public static string RemoveInstallation(string directory,bool preserve) {
  string root=Path.GetFullPath(directory).TrimEnd(Path.DirectorySeparatorChar);
  string project=Path.Combine(root,"Sakura"),marker=Path.Combine(root,".sakura-installation");
  if(root==Path.GetPathRoot(root).TrimEnd(Path.DirectorySeparatorChar)||!File.Exists(marker)||File.ReadAllText(marker).Trim()!=Marker
    ||!File.Exists(Path.Combine(project,"installed-files.tsv")))throw new IOException("This is not a verified Sakura installation folder.");
  var files=new List<string>();var dirs=new List<string>();Collect(root,files,dirs);
  // Check locks before moving user data or removing anything. Never kill an
  // unrelated Python process. The user must close Sakura before uninstalling.
  foreach(string file in files)using(var input=new FileStream(file,FileMode.Open,FileAccess.Read,FileShare.None)){}
  RemoveOwnedIntegrations(root,project);
  var installed=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
  foreach(string row in File.ReadAllLines(Path.Combine(project,"installed-files.tsv"))) {
   string[] fields=row.Split('\t');if(fields.Length!=2)continue;
   string path=Path.GetFullPath(Path.Combine(root,fields[1]));
   if(!path.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("Invalid installed file path.");
   installed[path]=fields[0];
  }
  string backup=null;
  foreach(string file in files) {
   string expected;bool original=false;
   if(installed.TryGetValue(file,out expected))using(var sha=SHA256.Create())using(var input=File.OpenRead(file))
    original=BitConverter.ToString(sha.ComputeHash(input)).Replace("-","").ToLowerInvariant()==expected;
   if(original||file==marker||file==Path.Combine(project,"installed-files.tsv")||file==Path.Combine(project,"INSTALLATION.txt"))continue;
   // Even "remove personal data" must not erase unrelated files placed next
   // to the app. Keep unowned files outside Sakura's private project folder.
   if(!preserve&&(file.StartsWith(project+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)||installed.ContainsKey(file)))continue;
   if(backup==null)backup=root+" - User data "+DateTime.Now.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N").Substring(0,6);
   string target=Path.Combine(backup,file.Substring(root.Length+1));Directory.CreateDirectory(Path.GetDirectoryName(target));File.Move(file,target);
  }
  // All paths were inventoried under the exact marked root, with junctions and
  // symlinks rejected. Delete only those files, then empty directories.
  foreach(string file in files)if(File.Exists(file))File.Delete(file);
  for(int i=dirs.Count-1;i>=0;i--)Directory.Delete(dirs[i],false);
  Directory.Delete(root,false);return backup;
 }
 static void Collect(string directory,List<string> files,List<string> dirs) {
  if((File.GetAttributes(directory)&FileAttributes.ReparsePoint)!=0)throw new IOException("Uninstall cannot follow linked folders. Remove the link and retry.");
  foreach(string file in Directory.GetFiles(directory)) {
   if((File.GetAttributes(file)&FileAttributes.ReparsePoint)!=0)throw new IOException("Uninstall cannot follow linked files.");files.Add(file);
  }
  foreach(string child in Directory.GetDirectories(directory)){dirs.Add(child);Collect(child,files,dirs);}
 }
 [STAThread] static void Main(string[] args) {
  Application.EnableVisualStyles();
  if(args.Length==4&&args[0]=="--cleanup") {
   try {
    int pid;if(!int.TryParse(args[2],out pid))throw new IOException("Invalid uninstall process.");
    try {using(var parent=Process.GetProcessById(pid))if(!parent.WaitForExit(15000))throw new IOException("The uninstall window did not close.");}catch(ArgumentException){}
    string root=Path.GetFullPath(args[1]).TrimEnd(Path.DirectorySeparatorChar);
    string backup=RemoveInstallation(root,args[3]=="keep");
    using(var key=Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\SakuraCompanion")) {
     if(key!=null&&string.Equals(Convert.ToString(key.GetValue("InstallLocation")),root,StringComparison.OrdinalIgnoreCase)) {
      key.Close();Registry.CurrentUser.DeleteSubKeyTree(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\SakuraCompanion",false);
     }
    }
    File.Delete(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"Sakura Companion.lnk"));
    string menu=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.StartMenu),"Programs","Sakura Companion");
    File.Delete(Path.Combine(menu,"Sakura Companion.lnk"));if(Directory.Exists(menu)&&Directory.GetFileSystemEntries(menu).Length==0)Directory.Delete(menu);
    MessageBox.Show("Sakura was uninstalled. The installation folder was removed."+(backup==null?"":"\nYour personal data was saved to:\n"+backup),"Sakura Companion");
   }catch(Exception error){MessageBox.Show("Uninstall did not finish. Close Sakura and retry.\n"+error.Message,"Sakura Companion");}
   finally {MoveFileEx(Application.ExecutablePath,null,4);}
   return;
  }
  string project=AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar),install=Path.GetDirectoryName(project);
  var choice=MessageBox.Show("Uninstall Sakura and remove its installation folder?\n\nYes: keep imported models, downloaded AI, settings and other personal files in a separate backup folder.\nNo: remove these files too.\nCancel: keep the app.\n\nClose Sakura before continuing.","Uninstall Sakura",MessageBoxButtons.YesNoCancel);
  if(choice==DialogResult.Cancel)return;
  try {
   string helper=Path.Combine(Path.GetTempPath(),"Sakura-Uninstall-"+Guid.NewGuid().ToString("N")+".exe");File.Copy(Application.ExecutablePath,helper);
   Process.Start(new ProcessStartInfo(helper,"--cleanup \""+install+"\" "+Process.GetCurrentProcess().Id+" "+(choice==DialogResult.Yes?"keep":"remove")){UseShellExecute=false,CreateNoWindow=true});
  }catch(Exception error){MessageBox.Show(error.Message,"Sakura Companion");}
 }
}
