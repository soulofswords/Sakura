"""Exercise the actual Java provider error classifier, without keys or API requests."""
from pathlib import Path
import subprocess
import tempfile

BASE=Path(__file__).resolve().parents[1]
java=next((BASE/'tools/android-cache/jdk').rglob('javac.exe')).parent
source=r'''
package app.sakura.mobile;
public class ProviderErrorChecks {
 static void require(boolean ok,String label){if(!ok)throw new AssertionError(label);}
 public static void main(String[] args){
  String key="sk-test-private-secret";
  String quota=ProviderErrors.describe("openai",429,"insufficient_quota","insufficient_quota","You exceeded your current quota, check your plan and billing.",null,key);
  require(quota.contains("billing limit")&&quota.contains("new key does not reset")&&quota.contains("ChatGPT subscription"),"Billing guidance");
  String rate=ProviderErrors.describe("openai",429,"rate_limit_exceeded","tokens","Rate limit reached", "12",key);
  require(rate.contains("after 12 seconds")&&!rate.contains("billing limit"),"Rate limit separate from billing");
  require(ProviderErrors.describe("gemini",403,"403","PERMISSION_DENIED","Project denied access",null,key).contains("project permissions"),"403 access guidance");
  require(ProviderErrors.describe("gemini",404,"404","NOT_FOUND","Model not found",null,key).contains("Find available models"),"404 model guidance");
  require(ProviderErrors.describe("gemini",400,"API_KEY_INVALID","INVALID_ARGUMENT","API key not valid",null,key).contains("key was rejected"),"Gemini invalid key");
  require(ProviderErrors.describe("gemini",429,"429","RESOURCE_EXHAUSTED","Quota exceeded, limit: 0",null,key).contains("billing limit"),"Zero quota");
  String secret=ProviderErrors.describe("openai",401,"invalid_api_key","invalid_request_error","Incorrect key "+key+" and AIzaPrivate0123456",null,key);
  require(!secret.contains(key)&&!secret.contains("AIzaPrivate0123456")&&secret.contains("[redacted]"),"Secret redaction");
  String html=ProviderErrors.describe("gemini",403,"","","",null,key);require(html.contains("Gemini HTTP 403"),"Non-JSON fallback");
  System.out.println("PASS: actual Java quota/rate-limit distinction, 403/404/invalid-key guidance and secret redaction");
 }
}
'''
with tempfile.TemporaryDirectory(prefix='provider-errors-',dir=BASE/'audit-results') as directory:
    work=Path(directory);harness=work/'ProviderErrorChecks.java';harness.write_text(source,encoding='utf-8')
    subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(work),str(BASE/'android/src/app/sakura/mobile/ProviderErrors.java'),str(harness)],check=True)
    subprocess.run([str(java/'java.exe'),'-cp',str(work),'app.sakura.mobile.ProviderErrorChecks'],check=True)
