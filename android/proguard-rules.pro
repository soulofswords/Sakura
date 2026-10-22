-keep public class app.sakura.mobile.MainActivity { *; }
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keepattributes RuntimeVisibleAnnotations,AnnotationDefault,InnerClasses,EnclosingMethod
-dontwarn java.lang.invoke.StringConcatFactory

-keep public class app.sakura.mobile.WakeService { *; }
-keep class org.vosk.** { *; }
-keep class com.sun.jna.** { *; }
-dontwarn java.awt.**
