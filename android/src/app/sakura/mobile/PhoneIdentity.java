package app.sakura.mobile;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

final class PhoneIdentity {
 static String proof(String token,String pc,String endpoint,String nonce)throws Exception {
  byte[] key=MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
  Mac mac=Mac.getInstance("HmacSHA256");mac.init(new SecretKeySpec(key,"HmacSHA256"));
  byte[] digest=mac.doFinal((pc+"\n"+endpoint+"\n"+nonce).getBytes(StandardCharsets.UTF_8));
  StringBuilder hex=new StringBuilder();for(byte b:digest)hex.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return hex.toString();
 }
 static boolean verify(String token,String expectedPc,String actualPc,String endpoint,String nonce,String echoedNonce,String actualProof)throws Exception {
  if(!actualPc.matches("[0-9a-f]{32}")||!nonce.equals(echoedNonce)||!actualProof.matches("[0-9a-f]{64}"))return false;
  if(!expectedPc.isEmpty()&&!expectedPc.equals(actualPc))return false;
  return MessageDigest.isEqual(proof(token,actualPc,endpoint,nonce).getBytes(StandardCharsets.US_ASCII),actualProof.getBytes(StandardCharsets.US_ASCII));
 }
}
