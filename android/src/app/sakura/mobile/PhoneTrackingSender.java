package app.sakura.mobile;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;

// One upload worker, one pending frame. A slow network never builds a stale queue.
final class PhoneTrackingSender implements AutoCloseable {
 interface Upload {void send(String frame)throws Exception;}
 interface Report {void update(int fps,long dropped,double uploadMs,String error);}
 private final ArrayBlockingQueue<String> pending=new ArrayBlockingQueue<>(1);
 private final Upload upload;private final Report report;private final Thread worker;
 private volatile boolean closed;private volatile long dropped;
 PhoneTrackingSender(Upload upload,Report report){this.upload=upload;this.report=report;worker=new Thread(this::run,"SakuraTrackingSender");worker.setDaemon(true);worker.start();}
 synchronized void submit(String frame){if(closed)return;if(!pending.offer(frame)){pending.poll();dropped++;pending.offer(frame);}}
 private void run(){long began=System.nanoTime();int sent=0;double uploadMs=0;String error="";
  while(!closed){try{
   String frame=pending.poll(200,TimeUnit.MILLISECONDS);if(frame==null)continue;
   long start=System.nanoTime();upload.send(frame);uploadMs+=(System.nanoTime()-start)/1000000.0;sent++;
  }catch(InterruptedException stopped){break;}catch(Exception failure){error=failure.getMessage()==null?"Tracking upload failed":failure.getMessage();try{Thread.sleep(100);}catch(InterruptedException stopped){break;}}
   long now=System.nanoTime();if(now-began>=1000000000L){report.update((int)Math.round(sent*1000000000.0/(now-began)),dropped,sent==0?0:uploadMs/sent,error);began=now;sent=0;uploadMs=0;error="";}
  }
 }
 public synchronized void close(){closed=true;pending.clear();worker.interrupt();}
}
