package app.sakura.mobile;

import android.webkit.JavascriptInterface;
import java.lang.reflect.Method;
import java.lang.reflect.InvocationTargetException;
import org.json.*;

/** Only the main document receives the random capability. Renderer frames do not. */
final class NativeGateway {
 private final Object target;
 private final String capability=java.util.UUID.randomUUID().toString()+java.util.UUID.randomUUID().toString();
 NativeGateway(Object target){this.target=target;}
 @JavascriptInterface public String invoke(String proof,String name,String arguments){
  try{
   if(!capability.equals(proof))throw new SecurityException("Native access denied.");
   if(arguments==null||arguments.length()>250000)throw new SecurityException("Native request too large.");
   JSONArray args=new JSONArray(arguments);
   for(Method method:target.getClass().getDeclaredMethods()){
    if(!method.getName().equals(name)||!method.isAnnotationPresent(JavascriptInterface.class))continue;
    Class<?>[] types=method.getParameterTypes();if(types.length!=args.length())continue;
    Object[] values=new Object[types.length];
    for(int i=0;i<types.length;i++){
     Object value=args.get(i);
     if(types[i]==String.class){if(!(value instanceof String))throw new SecurityException("Expected text.");values[i]=value;}
     else if(types[i]==boolean.class){if(!(value instanceof Boolean))throw new SecurityException("Expected a switch value.");values[i]=value;}
     else if(types[i]==double.class){if(!(value instanceof Number)||!Double.isFinite(((Number)value).doubleValue()))throw new SecurityException("Expected a finite number.");values[i]=((Number)value).doubleValue();}
     else throw new SecurityException("Unsupported native argument.");
    }
    method.setAccessible(true);
    return new JSONObject().put("value",JSONObject.wrap(method.invoke(target,values))).toString();
   }
   throw new SecurityException("Unsupported native method.");
  }catch(Exception error){try{return new JSONObject().put("error","Native request refused.").toString();}catch(Exception ignored){return "{}";}}
 }
 String bootstrap()throws Exception{
  JSONArray methods=new JSONArray();
  for(Method method:target.getClass().getDeclaredMethods())if(method.isAnnotationPresent(JavascriptInterface.class))methods.put(method.getName());
  return "<script>(()=>{const native=window._SakuraGateway,proof="+JSONObject.quote(capability)+",api={};for(const name of "+methods.toString()+")api[name]=(...args)=>{const result=JSON.parse(native.invoke(proof,name,JSON.stringify(args)));if(result.error)throw Error(result.error);return result.value;};Object.defineProperty(window,'Sakura',{value:Object.freeze(api),writable:false,configurable:false});})();</script>";
 }
}
