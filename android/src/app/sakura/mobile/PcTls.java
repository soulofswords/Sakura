package app.sakura.mobile;
import java.net.HttpURLConnection;
import java.security.MessageDigest;
import java.security.cert.Certificate;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/** Pins the self-signed certificate saved when this phone paired with a PC. */
final class PcTls {
 private static final ConcurrentHashMap<String,SSLSocketFactory> FACTORIES=new ConcurrentHashMap<>();
 static String fingerprint(Certificate certificate){
  try{
   byte[] digest=MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded());
   StringBuilder text=new StringBuilder();
   for(byte value:digest)text.append(String.format(Locale.ROOT,"%02x",value&255));
   return text.toString();
  }catch(Exception error){return "";}
 }
 static String presented(HttpURLConnection connection){
  try{
   if(!(connection instanceof HttpsURLConnection))return "";
   Certificate[] chain=((HttpsURLConnection)connection).getServerCertificates();
   return chain==null||chain.length==0?"":fingerprint(chain[0]);
  }catch(Exception error){return "";}
 }
 static SSLSocketFactory factory(String pin){
  String key=pin==null?"":pin.toLowerCase(Locale.ROOT);
  SSLSocketFactory existing=FACTORIES.get(key);
  if(existing!=null)return existing;
  try{
   SSLContext context=SSLContext.getInstance("TLS");
   context.init(null,new TrustManager[]{new Pin(key)},null);
   SSLSocketFactory created=context.getSocketFactory();
   SSLSocketFactory raced=FACTORIES.putIfAbsent(key,created);
   return raced==null?created:raced;
  }catch(Exception error){throw new IllegalStateException("TLS is unavailable on this phone.",error);}
 }
 /** The pin replaces hostname matching: the certificate itself is the identity. */
 static HostnameVerifier verifier(){return (host,session)->true;}
 private static final class Pin implements X509TrustManager {
  private final String pin;
  Pin(String pin){this.pin=pin;}
  @Override public void checkClientTrusted(X509Certificate[] chain,String authType)throws CertificateException{
   throw new CertificateException("The PC does not accept phone certificates.");
  }
  @Override public void checkServerTrusted(X509Certificate[] chain,String authType)throws CertificateException{
   if(chain==null||chain.length==0)throw new CertificateException("The PC presented no certificate.");
   chain[0].checkValidity();
   // An empty pin is only used while pairing; the pairing response must then
   // name the certificate that was just presented, and that value is pinned.
   if(!pin.isEmpty()&&!pin.equals(fingerprint(chain[0])))throw new CertificateException("This PC's certificate does not match the phone's saved pairing.");
  }
  @Override public X509Certificate[] getAcceptedIssuers(){return new X509Certificate[0];}
 }
}
