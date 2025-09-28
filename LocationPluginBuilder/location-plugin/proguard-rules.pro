# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.

# Keep UniApp plugin classes
-keep class com.example.location.LocationPlugin { *; }
-keep class * extends io.dcloud.feature.uniapp.common.UniModule { *; }

# Keep fastjson
-keep class com.alibaba.fastjson.** { *; }
-dontwarn com.alibaba.fastjson.**