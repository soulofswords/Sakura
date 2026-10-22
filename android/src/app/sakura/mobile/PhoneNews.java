package app.sakura.mobile;
import java.net.URLEncoder;
import java.util.concurrent.ConcurrentHashMap;
final class PhoneNews {
 static final ConcurrentHashMap<String,String> cache=new ConcurrentHashMap<>();
 static final ConcurrentHashMap<String,Long> updated=new ConcurrentHashMap<>();
 static String fetch(String request,String area)throws Exception{
  String query=NewsRules.query(request,area);
  if(query==null)throw new Exception("Choose a news city or state in Local settings, or ask for news in Mumbai or Maharashtra.");
  String key=query;Long time=updated.get(key);if(time!=null&&System.currentTimeMillis()-time<120000&&cache.containsKey(key))return cache.get(key);
  String url=query.isEmpty()?"https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en":"https://news.google.com/rss/search?q="+URLEncoder.encode(query+" when:1d","UTF-8")+"&hl=en-IN&gl=IN&ceid=IN:en";
  String rss=new String(PhoneAssistant.http(url,"GET","","",null,1000000,8000),"UTF-8");
  if(cache.size()>20){cache.clear();updated.clear();}cache.put(key,rss);updated.put(key,System.currentTimeMillis());return rss;
 }
}
