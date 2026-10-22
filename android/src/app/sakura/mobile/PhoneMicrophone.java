package app.sakura.mobile;
import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.speech.*;
import java.util.ArrayList;

/** One user-started speech turn; never records in the background or during playback. */
final class PhoneMicrophone {
 final MainActivity activity;SpeechRecognizer recognizer;boolean requested,permissionPending;
 PhoneMicrophone(MainActivity activity){this.activity=activity;}
 void state(boolean on,String message){activity.microphoneEvent(on,message,null);}
 void start(){
  requested=true;
  if(activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
   permissionPending=true;state(true,"Allow microphone access to speak");activity.requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},6);return;
  }
  if(!activity.phoneForeground)return;
  if(!SpeechRecognizer.isRecognitionAvailable(activity)){stop();state(false,"Speech input is unavailable. Install/enable a phone speech service or type your message.");return;}
  release();
  try{
   recognizer=SpeechRecognizer.createSpeechRecognizer(activity);
   final SpeechRecognizer session=recognizer;
   recognizer.setRecognitionListener(new RecognitionListener(){
    boolean active(){return requested&&recognizer==session;}
    public void onReadyForSpeech(Bundle b){if(active())state(true,"Listening… tap the red button to mute");}
    public void onBeginningOfSpeech(){}public void onRmsChanged(float rms){}public void onBufferReceived(byte[] b){}public void onEndOfSpeech(){if(active())state(true,"Recognizing…");}public void onPartialResults(Bundle b){}public void onEvent(int type,Bundle b){}
    public void onError(int error){if(!active())return;stop();state(false,error==SpeechRecognizer.ERROR_NO_MATCH||error==SpeechRecognizer.ERROR_SPEECH_TIMEOUT?"No speech detected. Tap the microphone to try again.":error==SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS?"Microphone permission is off. Enable it in Android settings or type instead.":"Speech input stopped ("+error+"). Tap to retry, or type your message.");}
    public void onResults(Bundle results){
     if(!active())return;ArrayList<String> words=results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
     String text=words==null||words.isEmpty()?"":words.get(0).trim();stop();
     if(text.isEmpty())state(false,"No speech detected. Tap to try again.");else activity.microphoneEvent(false,"Message recognized",text.substring(0,Math.min(10000,text.length())));
    }
   });
   state(true,"Starting microphone…");recognizer.startListening(new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS,false).putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,1));
  }catch(Exception error){stop();state(false,"Could not start microphone. You can type your message instead.");}
 }
 void permissionResult(){permissionPending=false;if(activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED&&requested){if(activity.phoneForeground)start();}else{stop();state(false,"Microphone permission was denied. You can type your message instead.");}}
 void resume(){if(requested&&!permissionPending&&recognizer==null)start();}
 void pause(){if(!permissionPending){stop();state(false,"Microphone off");}}
 void release(){SpeechRecognizer old=recognizer;recognizer=null;if(old!=null){old.cancel();old.destroy();}}
 void stop(){requested=false;release();}
}
