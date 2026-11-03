package app.sakura.mobile;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;

/** Encrypted archive payload validation. Imported dialogue has no tool authority. */
final class PhoneHistory {
 static String validate(String value)throws Exception{
  if(value==null||value.getBytes(StandardCharsets.UTF_8).length>1_000_000)throw new Exception("Conversation archive exceeds 1 MB.");
  JSONObject input=new JSONObject(value);JSONArray threads=input.getJSONArray("threads");
  if(input.getInt("version")!=1||threads.length()>20)throw new Exception("Keep at most 20 conversations.");
  String active=input.getString("active_id");HashSet<String> ids=new HashSet<>();JSONArray output=new JSONArray();
  for(int i=0;i<threads.length();i++){
   JSONObject thread=threads.getJSONObject(i);String id=thread.getString("id"),origin=thread.getString("origin"),title=thread.getString("title");
   if(!id.matches("[A-Za-z0-9_-]{1,100}")||!ids.add(id)||!origin.matches("mobile|pc-import")||title.length()>100)throw new Exception("Invalid conversation identity.");
   JSONArray messages=thread.getJSONArray("messages"),clean=new JSONArray();if(messages.length()>200)throw new Exception("Keep at most 200 messages per conversation.");
   for(int j=0;j<messages.length();j++){JSONObject message=messages.getJSONObject(j);String role=message.getString("role"),text=message.getString("content");if(!role.matches("user|assistant")||text.length()>16000||text.indexOf('\0')>=0)throw new Exception("Invalid conversation message.");clean.put(new JSONObject().put("role",role).put("content",text));}
   output.put(new JSONObject().put("id",id).put("origin",origin).put("title",title).put("source_device",thread.optString("source_device","").substring(0,Math.min(100,thread.optString("source_device","").length()))).put("snapshot_id",thread.optString("snapshot_id","").substring(0,Math.min(64,thread.optString("snapshot_id","").length()))).put("messages",clean));
  }
  if(!ids.contains(active))throw new Exception("Select a saved conversation.");
  return new JSONObject().put("version",1).put("active_id",active).put("threads",output).toString();
 }
}
