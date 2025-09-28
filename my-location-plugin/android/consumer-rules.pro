# Consumer ProGuard rules for location-plugin

# Keep UniApp plugin classes
-keep class com.example.location.LocationPlugin { *; }
-keep class * extends io.dcloud.feature.uniapp.common.UniModule { *; }