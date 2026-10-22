package app.sakura.mobile;
import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.media.*;
import android.os.*;
import android.speech.tts.*;
import java.io.*;
import java.security.KeyStore;
import java.util.*;
import java.util.concurrent.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import org.json.*;
import org.vosk.Model;
import org.vosk.Recognizer;
import com.sun.jna.NativeLibrary;

/** Opt-in, visible, offline wake detector. No WebView/model rendering runs here. */
public final class WakeService extends Service {
 static volatile WakeService live;static volatile boolean uiBusy,manual;
 static final String STOP="app.sakura.mobile.STOP_WAKE",CHANNEL="sakura-wake";
 volatile boolean stopped;volatile String phase="Stopped",failure="";volatile AudioRecord record;volatile MediaPlayer player;
 Model wakeModel;Thread worker;TextToSpeech tts;CountDownLatch ttsReady=new CountDownLatch(1);PowerManager.WakeLock lock;
 SharedPreferences prefs(){return getSharedPreferences("paired-pcs",0);}
 static void pauseManual(boolean value){manual=value;WakeService s=live;if(value&&s!=null)s.interruptAudio();}
 static void busy(boolean value){uiBusy=value;WakeService s=live;if(value&&s!=null)s.interruptAudio();}
 void interruptAudio(){AudioRecord r=record;if(r!=null)try{r.stop();}catch(Exception ignored){}}
 static boolean recording(){WakeService s=live;return s!=null&&s.record!=null;}
 boolean paused(){AudioManager audio=(AudioManager)getSystemService(AUDIO_SERVICE);int mode=audio.getMode();return uiBusy||manual||mode==AudioManager.MODE_IN_CALL||mode==AudioManager.MODE_IN_COMMUNICATION;}
 @Override public IBinder onBind(Intent intent){return null;}
 @Override public void onCreate(){super.onCreate();live=this;NotificationManager nm=getSystemService(NotificationManager.class);nm.createNotificationChannel(new NotificationChannel(CHANNEL,"Sakura wake phrase",NotificationManager.IMPORTANCE_LOW));tts=new TextToSpeech(this,status->ttsReady.countDown());}
 Notification notification(String text){
  Intent open=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_SINGLE_TOP);
  PendingIntent content=PendingIntent.getActivity(this,10,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  PendingIntent stop=PendingIntent.getService(this,11,new Intent(this,WakeService.class).setAction(STOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  return new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("Sakura wake phrase is on").setContentText(text).setContentIntent(content).setOngoing(true).setVisibility(Notification.VISIBILITY_PRIVATE).setCategory(Notification.CATEGORY_SERVICE).addAction(new Notification.Action.Builder(null,"Stop listening",stop).build()).build();
 }
 void status(String text){if(text.equals(phase))return;phase=text;prefs().edit().putString("wake-status",text).apply();getSystemService(NotificationManager.class).notify(81,notification(text));}
 @Override public int onStartCommand(Intent intent,int flags,int id){
  if(intent==null||STOP.equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
  if(worker!=null)return START_NOT_STICKY;
  try{if(Build.VERSION.SDK_INT>=29)startForeground(81,notification("Loading offline wake detector…"),ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);else startForeground(81,notification("Loading offline wake detector…"));
   if(!WakeAssets.ready(this))throw new IOException("Download the offline wake pack in Sakura first.");
   prefs().edit().putBoolean("wake-enabled",true).apply();stopped=false;
   PowerManager pm=(PowerManager)getSystemService(POWER_SERVICE);lock=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"Sakura:WakePhrase");lock.acquire(600000);
   worker=new Thread(this::runDetector,"SakuraWake");worker.start();
  }catch(Exception error){failure="Wake listener could not start. Open Sakura and check microphone permission.";prefs().edit().putString("wake-status",failure).apply();stopSelf();}
  return START_NOT_STICKY;
 }
 void renewLock(){if(!getSystemService(NotificationManager.class).areNotificationsEnabled()){failure="Wake listener stopped because notifications are disabled.";stopped=true;interruptAudio();return;}if(lock!=null&&!lock.isHeld())lock.acquire(600000);}
 void runDetector(){
  try(Model model=new Model(WakeAssets.model(this).getAbsolutePath())){
   wakeModel=model;
   String phrase=WakePhrase.validate(prefs().getString("wake-phrase","hey sakura"));
   for(String word:phrase.split(" "))if(NativeLibrary.getInstance("vosk").getFunction("vosk_model_find_word").invokeInt(new Object[]{model.getPointer(),word})<0)throw new IOException("Wake pack doesn't know '"+word+"'. Choose different English words.");
   try(Recognizer wake=new Recognizer(model,16000,new JSONArray().put(phrase).put("[unk]").toString())){
    while(!stopped){
     renewLock();if(paused()){status("Paused while another voice input, reply or call is active");Thread.sleep(500);continue;}
     status("Listening offline for “"+phrase+"”");wake.reset();boolean detected=listenWake(wake,phrase);if(!detected||stopped||paused())continue;
     status("Wake phrase heard · ask your question after the tone");tone();
     String command=listenCommand(model,phrase);if(stopped||paused())continue;
     if(!WakePhrase.meaningfulCommand(command)){status("No question heard · say the wake phrase to try again");Thread.sleep(500);continue;}
     if(MainActivity.deliverWakeCommand(command)){Thread.sleep(500);continue;}
     respond(command);
    }
   }
  }catch(Throwable error){if(!stopped){String message=error instanceof IOException?error.getMessage():"Wake listener unavailable on this device. Open Sakura to retry.";failure=message;prefs().edit().putString("wake-status",message).apply();}}
  finally{stopSelf();}
 }
 AudioRecord openRecorder()throws IOException{
  int minimum=AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);if(minimum<1)throw new IOException("This phone cannot open the wake microphone.");
  AudioRecord r=new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,Math.max(minimum,6400));
  if(r.getState()!=AudioRecord.STATE_INITIALIZED){r.release();throw new IOException("Microphone is busy or unavailable. Open Sakura and retry.");}
  record=r;r.startRecording();return r;
 }
 void closeRecorder(AudioRecord r){try{r.stop();}catch(Exception ignored){}r.release();if(record==r)record=null;}
 boolean confirmedWake(JSONObject result,String phrase)throws Exception{
  JSONArray words=result.optJSONArray("result");if(words==null)return false;double[] confidence=new double[words.length()];for(int i=0;i<words.length();i++)confidence[i]=words.getJSONObject(i).optDouble("conf",0);double duration=words.length()==0?0:words.getJSONObject(words.length()-1).optDouble("end",0)-words.getJSONObject(0).optDouble("start",0);return WakePhrase.confident(result.optString("text"),phrase,confidence,duration);
 }
 boolean listenWake(Recognizer wake,String phrase)throws Exception{
  AudioRecord r=openRecorder();short[] pcm=new short[3200];java.io.ByteArrayOutputStream utterance=new java.io.ByteArrayOutputStream();
  try{while(!stopped&&!paused()){renewLock();int n=r.read(pcm,0,pcm.length);if(n<=0){if(stopped||paused())break;throw new IOException("Wake microphone stopped. Open Sakura to retry.");}
   if(utterance.size()+n*2>256000){byte[] recent=utterance.toByteArray();utterance.reset();utterance.write(recent,Math.max(0,recent.length-192000),Math.min(192000,recent.length));}
   for(int i=0;i<n;i++){utterance.write(pcm[i]&255);utterance.write((pcm[i]>>8)&255);}
   if(!wake.acceptWaveForm(pcm,n))continue;
   JSONObject candidate=new JSONObject(wake.getResult());boolean accepted=false;
   // A limited grammar can force unrelated speech into its only known phrase.
   // Confirm the completed phrase independently with unrestricted recognition.
   if(WakePhrase.matches(candidate.optString("text"),phrase)){
    try(Recognizer verifier=new Recognizer(wakeModel,16000)){verifier.setWords(true);byte[] audio=utterance.toByteArray();for(int offset=0;offset<audio.length&&!accepted;offset+=6400){int count=Math.min(6400,audio.length-offset);byte[] piece=java.util.Arrays.copyOfRange(audio,offset,offset+count);if(verifier.acceptWaveForm(piece,piece.length))accepted=confirmedWake(new JSONObject(verifier.getResult()),phrase);}if(!accepted)accepted=confirmedWake(new JSONObject(verifier.getFinalResult()),phrase);}
   }
   byte[] tail=utterance.toByteArray();utterance.reset();utterance.write(tail,Math.max(0,tail.length-64000),Math.min(64000,tail.length));if(accepted)return true;
  }}finally{closeRecorder(r);}return false;
 }
 String listenCommand(Model model,String phrase)throws Exception{
  try(Recognizer speech=new Recognizer(model,16000)){
   AudioRecord r=openRecorder();short[] pcm=new short[3200];long deadline=SystemClock.elapsedRealtime()+14000;
   try{while(!stopped&&!paused()&&SystemClock.elapsedRealtime()<deadline){int n=r.read(pcm,0,pcm.length);if(n<=0)break;if(speech.acceptWaveForm(pcm,n)){String text=WakePhrase.trimCommand(new JSONObject(speech.getResult()).optString("text"),phrase);if(!WakePhrase.meaningfulCommand(text))return "";return text;}}String text=WakePhrase.trimCommand(new JSONObject(speech.getFinalResult()).optString("text"),phrase);return WakePhrase.meaningfulCommand(text)?text:"";}finally{closeRecorder(r);}
  }
 }
 void tone(){try{ToneGenerator tone=new ToneGenerator(AudioManager.STREAM_NOTIFICATION,40);tone.startTone(ToneGenerator.TONE_PROP_BEEP,100);Thread.sleep(200);tone.release();}catch(Exception ignored){}}
 String key()throws Exception{String encrypted=prefs().getString("local-key","");String[] parts=encrypted.split(":",2);if(parts.length!=2)throw new IOException("Add your API key in Sakura Local settings.");KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,store.getKey("SakuraPairing",null),new GCMParameterSpec(128,android.util.Base64.decode(parts[0],0)));return new String(cipher.doFinal(android.util.Base64.decode(parts[1],0)),"UTF-8");}
 void respond(String command)throws Exception{
  status("Thinking · microphone paused");String provider=prefs().getString("local-provider","gemini"),secret=key();JSONArray history=new JSONArray(prefs().getString("wake-history","[]"));while(history.length()>18)history.remove(0);history.put(new JSONObject().put("role","user").put("content",command));
  PhoneAssistant assistant=new PhoneAssistant(this);String reply;
  try{reply=assistant.reply(history,provider,secret,prefs().getString("local-model","gemini-flash-latest"),prefs().getString("local-address","sir")).getString("reply");}catch(Exception error){reply="I couldn't complete that request. Open Sakura to check your connection or API quota.";}
  if(stopped||paused())return;history.put(new JSONObject().put("role","assistant").put("content",reply));prefs().edit().putString("wake-history",history.toString()).putLong("wake-history-time",System.currentTimeMillis()).apply();
  status("Speaking · microphone paused");
  try{String audio=assistant.speech(reply,provider,secret,prefs().getString("local-voice","female"),new File(getFilesDir(),"audio"));if(stopped||paused())return;File file=new File(getFilesDir(),"audio/"+audio.substring(audio.lastIndexOf('/')+1));play(file);}
  catch(Exception error){if(!stopped&&!paused())speakFallback(reply);}
 }
 void play(File file)throws Exception{
  CountDownLatch done=new CountDownLatch(1);MediaPlayer p=new MediaPlayer();player=p;
  try{p.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());p.setDataSource(file.getAbsolutePath());p.setOnCompletionListener(x->done.countDown());p.setOnErrorListener((x,w,e)->{done.countDown();return true;});p.prepare();if(stopped||paused())return;p.start();long end=SystemClock.elapsedRealtime()+90000;while(!stopped&&!paused()&&SystemClock.elapsedRealtime()<end&&!done.await(200,TimeUnit.MILLISECONDS)){} }finally{player=null;p.release();}
 }
 void speakFallback(String text)throws Exception{
  ttsReady.await(4,TimeUnit.SECONDS);if(stopped||paused()||tts==null)return;CountDownLatch done=new CountDownLatch(1);tts.setLanguage(text.matches("(?s).*[\\u0900-\\u097f].*")?new Locale("hi","IN"):Locale.ENGLISH);tts.setOnUtteranceProgressListener(new UtteranceProgressListener(){public void onStart(String id){}public void onDone(String id){done.countDown();}public void onError(String id){done.countDown();}});tts.speak(PhoneConversation.spoken(NewsRules.spoken(text)),TextToSpeech.QUEUE_FLUSH,null,"wake-reply");long end=SystemClock.elapsedRealtime()+90000;while(!stopped&&!paused()&&SystemClock.elapsedRealtime()<end&&!done.await(200,TimeUnit.MILLISECONDS)){}tts.stop();
 }
 @Override public void onDestroy(){stopped=true;interruptAudio();MediaPlayer p=player;if(p!=null)try{p.stop();}catch(Exception ignored){}if(tts!=null){tts.stop();tts.shutdown();}if(lock!=null&&lock.isHeld())lock.release();prefs().edit().putBoolean("wake-enabled",false).putString("wake-status",failure.isEmpty()?"Wake phrase off":failure).apply();if(live==this)live=null;manual=false;stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();}
}
