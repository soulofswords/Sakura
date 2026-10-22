"""Run real Java downloader against a controlled HTTP server; no phone/network needed."""
from pathlib import Path
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import tempfile
import threading

BASE=Path(__file__).resolve().parents[1]
java=next((BASE/'tools/android-cache/jdk').rglob('javac.exe')).parent
data=bytes(range(256))*4000
requests=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        start=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0]);requests.append((self.path,start))
        if self.path=='/failed':self.send_error(503);return
        if self.path=='/ignore':start=0
        self.send_response(206 if start else 200)
        if start:self.send_header('Content-Range',f'bytes {start}-{len(data)-1}/{len(data)}')
        self.send_header('Content-Length',str(len(data)-start));self.end_headers()
        body=data[start:]
        if self.path=='/broken' and start==0:body=body[:200000]
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
harness=r'''
package app.sakura.mobile;
import java.io.*;
public class DownloadChecks {
 public static void main(String[] args)throws Exception{
  File file=new File(args[1]);
  try{ResumableDownload.fetch(args[0],file,Long.parseLong(args[2]),args[3],1500,message->{});if(args[4].equals("fail"))throw new AssertionError("Expected failure");}
  catch(IOException error){if(!args[4].equals("fail"))throw error;if(file.length()==0)throw new AssertionError("Interrupted bytes lost");}
 }
}
'''
try:
    with tempfile.TemporaryDirectory() as directory:
        out=Path(directory);source=out/'DownloadChecks.java';source.write_text(harness,encoding='utf-8')
        subprocess.run([java/'javac.exe','-encoding','UTF-8','-d',out,BASE/'android/src/app/sakura/mobile/ResumableDownload.java',source],check=True)
        def run(endpoint,file,mode='ok'):
            subprocess.run([java/'java.exe','-cp',out,'app.sakura.mobile.DownloadChecks',f'http://127.0.0.1:{server.server_port}/{endpoint}',file,str(len(data)),hashlib.sha256(data).hexdigest(),mode],check=True)
        partial=out/'partial';run('broken',partial);assert partial.read_bytes()==data
        assert ('/broken',200000) in requests,'Retry must resume the interrupted connection'
        partial.write_bytes(data[:300000]);run('failed',partial,'fail');assert partial.read_bytes()==data[:300000]
        run('resume',partial);assert ('/resume',300000) in requests;assert partial.read_bytes()==data
        partial.write_bytes(data[:123000]);run('ignore',partial);assert partial.read_bytes()==data,'Server without Range restarts safely instead of appending duplicate bytes'
        partial.write_bytes(b'x'*len(data));run('resume',partial);assert partial.read_bytes()==data,'Corrupt complete partial discarded and verified download retried'
    print('PASS: actual Java interrupted-download resume, persistent bytes across failed attempts, safe no-Range fallback and corrupt-file SHA-256 recovery')
finally:server.shutdown();server.server_close()
