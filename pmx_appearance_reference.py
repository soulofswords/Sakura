"""Capture a real PMX Editor reference in a bounded, owned native process.

The small opt-in plugin reads one private job and exports the editor's Direct3D
render target. It never saves a model or changes existing editor windows.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time

from pmx_editor import model_file, find_editor

_LOCK = threading.Lock()
_PLUGIN_NAME = 'SakuraAppearanceReference.dll'

_PLUGIN_SOURCE = r'''using System;
using System.IO;
using System.Drawing;
using System.Reflection;
using System.Collections.Generic;
using System.Linq;
using PEPlugin.Pmx;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using PEPlugin;
using SlimDX.Direct3D9;

// Opt-in startup plugin. Only a Sakura-owned editor with a private job directory
// exports a reference; ordinary PMX Editor launches are unaffected.
public sealed class SakuraAppearanceReference : PEPluginClass {
    Timer timer;
    string folder;
    IPEConnector connector;
    int ticks;
    bool handling;
    Device device;
    bool[] enabled;
    int[] selected;
    int part=-1;
    List<object> parts=new List<object>();

    public SakuraAppearanceReference() {
        m_option = new PEPluginOption(true, false, "Sakura appearance reference");
    }
    public override void Run(IPERunArgs args) {
        folder = Environment.GetEnvironmentVariable("SAKURA_PMX_REFERENCE_JOB");
        if (String.IsNullOrEmpty(folder) || !File.Exists(Path.Combine(folder,"model.txt"))) return;
        connector = args.Host.Connector;
        timer = new Timer(); timer.Interval = 500;
        timer.Tick += Tick; timer.Start();
    }
    void Finish(object result) {
        timer.Stop();
        string temp=Path.Combine(folder,"result.tmp");
        File.WriteAllText(temp,new JavaScriptSerializer { MaxJsonLength=33554432 }.Serialize(result));
        File.Move(temp,Path.Combine(folder,"result.json"));
        Application.Exit();
    }
    void Capture(Device device,string file) {
        // SlimDX's object table can return the editor-owned wrapper here.
        // Disposing it destroys the editor's live render target on next draw.
        var source=device.GetRenderTarget(0);
        var description=source.Description;
        using(var resolved=Surface.CreateRenderTarget(device,description.Width,description.Height,description.Format,MultisampleType.None,0,false)) {
            device.StretchRectangle(source,resolved,TextureFilter.None);
            using(var stream=Surface.ToStream(resolved,ImageFileFormat.Png))
            using(var output=File.Create(file))stream.CopyTo(output);
        }
    }
    void Tick(object sender,EventArgs args) {
        if(handling)return;handling=true;
        try {
            ticks++;
            if(ticks==3) {
                string model=File.ReadAllText(Path.Combine(folder,"model.txt"));
                if(!connector.Form.OpenPMXFile(model))throw new Exception("PMX Editor could not load the model.");
                var settings=connector.View.PmxViewSetting;
                settings.Visible_Bone=false;settings.Visible_Vertex=false;settings.Visible_SelectedVertex=false;
                settings.Visible_SelectedFace=false;settings.Visible_Normal=false;settings.Visible_Body=false;
                settings.Visible_Joint=false;settings.BackColor=Color.Black;
                object nativeView=connector.View.PmxView;
                object nativeDraw=nativeView.GetType().GetProperty("PmxDraw").GetValue(nativeView,null);
                var axis=nativeDraw.GetType().GetProperty("EnableAxis");if(axis!=null)axis.SetValue(nativeDraw,false,null);
                string directionFile=Path.Combine(folder,"direction.json");
                if(File.Exists(directionFile)) {
                    float[] direction=new JavaScriptSerializer().Deserialize<float[]>(File.ReadAllText(directionFile));
                    if(direction!=null && direction.Length==3) {
                        var view=connector.View.PmxView;var position=view.CameraPosition;var target=view.CameraTarget;
                        double distance=Math.Sqrt(Math.Pow(position.X-target.X,2)+Math.Pow(position.Y-target.Y,2)+Math.Pow(position.Z-target.Z,2));
                        position.X=target.X+(float)distance*direction[0];position.Y=target.Y+(float)distance*direction[1];position.Z=target.Z-(float)distance*direction[2];view.CameraPosition=position;
                    }
                }
                connector.View.PmxView.UpdateView();
            }
            if(ticks<9)return;
            if(device==null) {
                object view=connector.View.PmxView;
                object draw=view.GetType().GetProperty("PmxDraw").GetValue(view,null);
                object manager=draw.GetType().GetProperty("Manager").GetValue(draw,null);
                device=(Device)manager.GetType().GetProperty("Direct3DDevice").GetValue(manager,null);
                object shadowModel=draw.GetType().GetProperty("PmxModel").GetValue(draw,null);
                var floor=shadowModel.GetType().GetProperty("ShowFloorShadow");if(floor!=null)floor.SetValue(shadowModel,false,null);
                Capture(device,Path.Combine(folder,"reference.png"));
                var pmx=connector.Pmx.GetCurrentState();
                selected=Enumerable.Range(0,pmx.Material.Count).Where(i=>pmx.Material[i].Diffuse.W>=0.99f).OrderByDescending(i=>pmx.Material[i].Faces.Count).Take(6).ToArray();
                object nativeModel=draw.GetType().GetProperty("PmxModel").GetValue(draw,null);
                var enableField=nativeModel.GetType().GetField("EnableParts");
                if(enableField==null)throw new Exception("Editor material visibility export is unavailable.");
                enabled=(bool[])enableField.GetValue(nativeModel);
            }
            if(part>=0) {
                int index=selected[part];string image=Path.Combine(folder,"part-"+index+".png");Capture(device,image);
                parts.Add(new {material=index,image="data:image/png;base64,"+Convert.ToBase64String(File.ReadAllBytes(image))});
            }
            part++;
            if(part>=selected.Length) {
                var lighting=connector.View.PmxViewSetting;
                Finish(new {ok=true,ambient=new[]{lighting.AmbientColor.R,lighting.AmbientColor.G,lighting.AmbientColor.B},light=new[]{lighting.LightColor.R,lighting.LightColor.G,lighting.LightColor.B},toon=lighting.ToonType.ToString(),shader=connector.View.PmxView.IsShaderMode,parts=parts});
                return;
            }
            connector.View.PmxViewHelper.PartsSelect.SetCheckedMaterialIndices(new int[]{selected[part]});
            connector.View.PmxViewHelper.PartsSelect.SelectedPartsVisible=true;
            connector.View.PmxView.UpdateView();
        } catch(Exception ex) {
            try {Finish(new {ok=false,error="PMX Editor reference export failed: "+ex.ToString()});}
            catch {timer.Stop();Application.Exit();}
        } finally {handling=false;}
    }
}
'''


def _direction(values):
    if not isinstance(values,list) or len(values)!=3:
        raise ValueError('Supply a three-component viewing direction.')
    import math
    if any(type(value) not in (int,float) or not math.isfinite(value) for value in values):
        raise ValueError('Viewing direction must contain finite numbers.')
    length=math.sqrt(sum(value*value for value in values))
    if not .0001 < length < 1e6:raise ValueError('Invalid viewing direction.')
    return [value/length for value in values]


def _editor_process_running(editor):
    import psutil
    try:
        for process in psutil.process_iter(['name']):
            try:
                if (process.info.get('name') or '').casefold()==editor.name.casefold():
                    return True
            except psutil.Error:
                return True  # An unreadable process is not proof of a dead job.
    except psutil.Error:
        return True
    return False


def _acquire_slot_lock(target):
    # Windows releases this byte-range lock on a process crash. Keep the lock
    # file in place: unlinking it would let two jobs lock different file objects.
    import msvcrt
    stream=target.with_name(target.name+'.lock').open('a+b')
    try:
        if stream.seek(0,2)==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        return stream
    except OSError as exc:
        stream.close()
        raise RuntimeError('A PMX Editor appearance comparison is already running in another Sakura instance.') from exc


def _prepare_slot(target, binary, editor):
    marker=target.with_name(target.name+'.owner.json')
    source_hash=hashlib.sha256(_PLUGIN_SOURCE.encode('utf-8')).hexdigest()
    proof=None
    if marker.is_file() and marker.stat().st_size<4096:
        try:proof=json.loads(marker.read_text(encoding='utf-8'))
        except (ValueError,OSError):pass
    known=isinstance(proof,dict) and proof.get('source_sha256')==source_hash
    if target.exists():
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if not known or proof.get('sha256')!=digest:
            raise RuntimeError('The reference plugin slot is occupied by an unverified file; it was not changed.')
        if _editor_process_running(editor):
            raise RuntimeError('A reference plugin remains from an earlier job. Close PMX Editor before retrying; active editor files were not changed.')
        target.unlink()
    if marker.exists():
        if not known:raise RuntimeError('The reference plugin ownership record is unverified; it was not changed.')
        marker.unlink()
    digest=hashlib.sha256(binary).hexdigest()
    with marker.open('x',encoding='utf-8') as stream:
        json.dump({'sha256':digest,'source_sha256':source_hash},stream)
    try:
        with target.open('xb') as stream:stream.write(binary)
    except Exception:
        marker.unlink(missing_ok=True)
        raise
    return target,bytes.fromhex(digest)


def capture_reference(model, direction, editor_path=None, timeout=35):
    file=model_file(model)
    values=_direction(direction)
    if os.name!='nt':raise RuntimeError('Automatic PMX Editor matching requires Windows.')
    editor=find_editor(editor_path)
    if editor is None:raise RuntimeError('Configure PMX Editor before matching its appearance.')
    if not _LOCK.acquire(blocking=False):raise RuntimeError('A PMX Editor appearance comparison is already running.')
    process=None;installed=None;slot_lock=None
    try:
        framework=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not framework.is_file():raise RuntimeError('The .NET Framework C# compiler is unavailable.')
        references=[editor.parent/'Lib/PEPlugin/PEPlugin.dll',editor.parent/'Lib/SlimDX/SlimDX.dll']
        if any(not path.is_file() for path in references):raise RuntimeError('PMX Editor plugin libraries are missing.')
        with tempfile.TemporaryDirectory(prefix='sakura-pmx-reference-') as temporary:
            job=Path(temporary);source=job/'ReferencePlugin.cs';dll=job/_PLUGIN_NAME
            source.write_text(_PLUGIN_SOURCE,encoding='utf-8')
            command=[str(framework),'/nologo','/target:library','/out:'+str(dll),'/r:System.Drawing.dll','/r:System.Windows.Forms.dll','/r:System.Web.Extensions.dll']
            command+=['/r:'+str(path) for path in references]+[str(source)]
            compiled=subprocess.run(command,capture_output=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
            if compiled.returncode:raise RuntimeError('PMX Editor reference plugin could not be compiled for this installation.')
            target=editor.parent/'_plugin/User'/_PLUGIN_NAME
            target.parent.mkdir(parents=True,exist_ok=True)
            slot_lock=_acquire_slot_lock(target)
            installed=_prepare_slot(target,dll.read_bytes(),editor)
            (job/'model.txt').write_text(str(file),encoding='utf-8')
            (job/'direction.json').write_text(json.dumps(values),encoding='utf-8')
            environment=dict(os.environ,SAKURA_PMX_REFERENCE_JOB=str(job))
            process=subprocess.Popen([str(editor)],cwd=str(editor.parent),env=environment,creationflags=subprocess.CREATE_NO_WINDOW)
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                report=job/'result.json'
                if report.is_file():break
                if process.poll() is not None:raise RuntimeError('PMX Editor closed before returning an appearance reference.')
                time.sleep(.1)
            else:raise RuntimeError('PMX Editor reference timed out. The owned editor was stopped; appearance settings were not changed.')
            if report.stat().st_size>32*1024*1024:raise RuntimeError('Invalid PMX Editor reference report.')
            data=json.loads(report.read_text(encoding='utf-8-sig'))
            if not data.get('ok'):raise RuntimeError('PMX Editor could not export this model. Check that the model opens without errors.')
            image=job/'reference.png'
            if not image.is_file() or not 100 < image.stat().st_size <= 16*1024*1024:raise RuntimeError('PMX Editor did not return a valid reference image.')
            from PIL import Image
            import io
            raw=image.read_bytes()
            with Image.open(io.BytesIO(raw)) as pixels:
                if pixels.format!='PNG' or pixels.width*pixels.height>16000000:raise RuntimeError('PMX Editor reference image exceeds supported dimensions.')
                pixels.load()
            parts=data.get('parts',[])
            if not isinstance(parts,list) or not 0<=len(parts)<=6:raise RuntimeError('PMX Editor did not return material references.')
            for part in parts:
                if not isinstance(part,dict) or type(part.get('material')) is not int or not 0<=part['material']<4096:raise RuntimeError('Invalid editor material reference.')
                encoded=part.get('image','')
                if not isinstance(encoded,str) or not encoded.startswith('data:image/png;base64,') or len(encoded)>8*1024*1024:raise RuntimeError('Invalid editor material image.')
                try:
                    decoded=base64.b64decode(encoded.split(',',1)[1],validate=True)
                    with Image.open(io.BytesIO(decoded)) as pixels:
                        if pixels.format!='PNG' or pixels.width*pixels.height>16000000:raise ValueError('Invalid material image dimensions.')
                        pixels.load()
                except (ValueError,OSError) as exc:raise RuntimeError('The editor material image could not be decoded.') from exc
            return {'model':model,'image':'data:image/png;base64,'+base64.b64encode(raw).decode('ascii'),
                    'parts':parts,
                    'lighting':{key:data.get(key) for key in ('ambient','light','toon','shader')},'source':'PMX Editor Direct3D render target'}
    except PermissionError as exc:
        raise RuntimeError('PMX Editor plugin folder is not writable. Use a user-writable editor installation.') from exc
    finally:
        try:
            if process is not None:
                if process.poll() is None:process.terminate()
                try:process.wait(timeout=4)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=4)
        finally:
            try:
                if installed:
                    target,digest=installed
                    if target.is_file() and hashlib.sha256(target.read_bytes()).digest()==digest:
                        target.unlink()
                        marker=target.with_name(target.name+'.owner.json')
                        try:
                            proof=json.loads(marker.read_text(encoding='utf-8'))
                            if isinstance(proof,dict) and proof.get('sha256')==digest.hex():marker.unlink()
                        except (OSError,ValueError):pass
            finally:
                try:
                    if slot_lock is not None:slot_lock.close()
                finally:_LOCK.release()
