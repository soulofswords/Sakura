package app.sakura.mobile;
import java.util.Locale;

final class ProviderErrors {
 static String describe(String provider,int status,String code,String type,String message,String retryAfter,String key){
  String name=provider.equals("gemini")?"Gemini":provider.equals("openai")?"OpenAI":"Service";
  String details=(code+" "+type+" "+message).toLowerCase(Locale.ROOT),hint;
  boolean billing=details.contains("insufficient_quota")||details.contains("billing")||details.contains("credit")||details.contains("spend_limit")||details.contains("usage_limit")||details.contains("budget")||details.contains("quota limit: 0")||details.contains("limit: 0");
  if(status==429&&billing)hint="API quota or billing limit reached. A new key does not reset the same project's quota. Check API credits, billing and project usage limits in "+(provider.equals("gemini")?"Google AI Studio.":"the OpenAI API dashboard. A ChatGPT subscription does not include API credit.");
  else if(status==429)hint="Request rate or quota limit reached. "+(retryAfter!=null&&retryAfter.matches("[0-9]{1,6}")?"Try again after "+retryAfter+" seconds. ":"Wait before trying again. ")+"Check this project's request/token limits and available API quota. No automatic repeated requests were sent.";
  else if(status==401||details.contains("api_key_invalid")||details.contains("api key not valid"))hint="The API key was rejected. Enter a key issued by the selected provider and save it. Check that it has not expired or been revoked.";
  else if(status==403)hint="Access was denied. Check the selected provider's project permissions, API/key restrictions, regional availability and account access. Trying another model will not remove a project-level block.";
  else if(status==404||details.contains("model_not_found"))hint="The selected model is unavailable for this key or API endpoint. Use Find available models and choose a supported chat model, then save. Do not enter a model's display name or a full URL.";
  else if(status==400)hint="The provider rejected the request. Check the selected model and its supported API features.";
  else if(status>=500)hint="The provider is temporarily unavailable. Try again later.";
  else hint="Request failed. Check your internet connection and provider settings.";
  String safe=message==null?"":message;
  if(key!=null&&!key.isEmpty())safe=safe.replace(key,"[redacted]");
  safe=safe.replaceAll("(?i)(?:sk-[A-Za-z0-9_-]{4,}|AIza[A-Za-z0-9_-]{4,}|Bearer\\s+[^\\s]+)","[redacted]").replaceAll("[\\r\\n\\t]+"," ").trim();
  if(safe.length()>420)safe=safe.substring(0,420)+"…";
  String errorCode=code==null?"":code.replaceAll("[^A-Za-z0-9_.-]","");if(errorCode.length()>80)errorCode=errorCode.substring(0,80);
  return name+" HTTP "+status+(errorCode.isEmpty()?"":" ["+errorCode+"]")+": "+hint+(safe.isEmpty()?"":"\nProvider detail: "+safe);
 }
}
