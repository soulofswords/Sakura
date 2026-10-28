package app.sakura.mobile;
import org.json.*;

/** Network bytes are data, never a JavaScript expression. */
final class NativeReplies {
 static String script(String id,String result){
  String safe;
  try{
   if(result==null||result.length()>2000000)throw new JSONException("Invalid reply");
   JSONTokener input=new JSONTokener(result);Object value=input.nextValue();
   if(!(value instanceof JSONObject)||input.nextClean()!=0)throw new JSONException("Invalid reply");
   safe=value.toString();
  }
  catch(Exception ignored){safe="{\"error\":\"PC returned an invalid JSON response.\"}";}
  return "window.sakuraNativeReply?.("+JSONObject.quote(id)+",JSON.parse("+JSONObject.quote(safe)+"))";
 }
}
