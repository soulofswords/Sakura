package app.sakura.mobile;
import android.Manifest;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.provider.ContactsContract;
import android.telephony.PhoneStateListener;
import android.telephony.TelephonyManager;
import java.util.*;

/** Explicit user call requests only. No AI-generated number is executed. */
final class CallController {
 final MainActivity activity;String pending="";boolean muted=false,started=false,sawCall=false;
 final TelephonyManager manager;PhoneStateListener listener;long launchedAt=0;
 CallController(MainActivity activity){this.activity=activity;manager=(TelephonyManager)activity.getSystemService(android.content.Context.TELEPHONY_SERVICE);}
 void request(String person){activity.runOnUiThread(()->{
  if(!pending.isEmpty()||muted){message("A call request is already active.");return;}
  pending=person;
  ArrayList<String> permissions=new ArrayList<>();
  for(String p:new String[]{Manifest.permission.CALL_PHONE,Manifest.permission.READ_PHONE_STATE})if(activity.checkSelfPermission(p)!=PackageManager.PERMISSION_GRANTED)permissions.add(p);
  if(!person.matches("[+0-9 ()-]{3,30}")&&activity.checkSelfPermission(Manifest.permission.READ_CONTACTS)!=PackageManager.PERMISSION_GRANTED)permissions.add(Manifest.permission.READ_CONTACTS);
  if(!permissions.isEmpty())activity.requestPermissions(permissions.toArray(new String[0]),3);else resolve();
 });}
 void permissions(){if(activity.checkSelfPermission(Manifest.permission.CALL_PHONE)!=PackageManager.PERMISSION_GRANTED||activity.checkSelfPermission(Manifest.permission.READ_PHONE_STATE)!=PackageManager.PERMISSION_GRANTED){pending="";message("Calling permission was not granted. No call was placed.");return;}resolve();}
 void resolve(){
  final String person=pending;ArrayList<String[]> matches=new ArrayList<>();
  if(person.matches("[+0-9 ()-]{3,30}"))matches.add(new String[]{person,person.replaceAll("[ ()-]","")});
  else{
   if(activity.checkSelfPermission(Manifest.permission.READ_CONTACTS)!=PackageManager.PERMISSION_GRANTED){pending="";message("Contacts permission was not granted. No call was placed.");return;}
   try(Cursor cursor=activity.getContentResolver().query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI,new String[]{ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,ContactsContract.CommonDataKinds.Phone.NUMBER},null,null,null)){
    Set<String> seen=new HashSet<>();if(cursor!=null)while(cursor.moveToNext()){String name=cursor.getString(0),number=cursor.getString(1);if(name!=null&&name.equalsIgnoreCase(person)&&number!=null&&seen.add(number))matches.add(new String[]{name,number});}
   }catch(Exception error){pending="";message("Contacts could not be read. No call was placed.");return;}
  }
  if(matches.isEmpty()){pending="";message("No matching contact was found. Say the full contact name or phone number.");return;}
  if(matches.size()==1){confirm(matches.get(0));return;}
  String[] labels=new String[matches.size()];for(int i=0;i<labels.length;i++)labels[i]=matches.get(i)[0]+" — "+matches.get(i)[1];
  new AlertDialog.Builder(activity).setTitle("Choose a contact number").setItems(labels,(dialog,index)->confirm(matches.get(index))).setNegativeButton("Cancel",(d,w)->pending="").setOnCancelListener(d->pending="").show();
 }
 void confirm(String[] contact){new AlertDialog.Builder(activity).setTitle("Call "+contact[0]+"?").setMessage(contact[1]+"\nSakura will stay muted until the call ends.").setPositiveButton("Call",(d,w)->dial(contact[1])).setNegativeButton("Cancel",(d,w)->pending="").setOnCancelListener(d->pending="").show();}
 void dial(String raw){
  String number=raw.replaceAll("[ ()-]","");pending="";
  if(!number.matches("\\+?[0-9]{3,20}")){message("Unsupported phone number. No call was placed.");return;}
  try{
   started=false;sawCall=false;listener=new PhoneStateListener(){@Override public void onCallStateChanged(int state,String incoming){if(state!=TelephonyManager.CALL_STATE_IDLE){sawCall=true;setMuted(true);}else if(started&&sawCall)finish();}};
   manager.listen(listener,PhoneStateListener.LISTEN_CALL_STATE);setMuted(true);started=true;launchedAt=System.currentTimeMillis();
   activity.startActivity(new Intent(Intent.ACTION_CALL,Uri.fromParts("tel",number,null)));
  }catch(Exception error){finish();message("The phone could not start the call.");}
 }
 boolean inCall(){if(muted)return true;try{return activity.checkSelfPermission(Manifest.permission.READ_PHONE_STATE)==PackageManager.PERMISSION_GRANTED&&manager!=null&&manager.getCallState()!=TelephonyManager.CALL_STATE_IDLE;}catch(Exception ignored){return muted;}}
 void resume(){if(!muted||!started)return;try{if(manager.getCallState()==TelephonyManager.CALL_STATE_IDLE&&(sawCall||System.currentTimeMillis()-launchedAt>3000))finish();}catch(Exception ignored){/* Keep muted if call state cannot be verified. */}}
 void setMuted(boolean value){muted=value;activity.callState(value);}
 void finish(){started=false;sawCall=false;setMuted(false);if(listener!=null&&manager!=null){manager.listen(listener,PhoneStateListener.LISTEN_NONE);listener=null;}}
 void message(String text){activity.phoneNotice(text);}
 void close(){if(listener!=null&&manager!=null)manager.listen(listener,PhoneStateListener.LISTEN_NONE);}
}
