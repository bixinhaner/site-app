package com.example.location;

import android.Manifest;
import android.content.Context;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.location.Geocoder;
import android.location.Address;
import android.os.Bundle;
import android.os.Looper;
import android.util.Log;

// 使用 Weex SDK (包含在 AAR 中)
import org.json.JSONObject;
import org.json.JSONException;
import org.json.JSONArray;
import com.taobao.weex.annotation.JSMethod;
import com.taobao.weex.bridge.JSCallback;
import com.taobao.weex.common.WXModule;

import java.util.List;
import java.util.Locale;

/**
 * UniApp 自定义原生定位插件
 * 使用 Weex SDK 注解 (与 UniApp 兼容)
 * 使用 Android 原生 JSONObject 避免依赖冲突
 * 
 * @author Site Management System
 * @version 1.0.1-android-json
 */
public class LocationPlugin extends WXModule { // 继承 WXModule (Weex 基类)
    
    private static final String TAG = "LocationPlugin";
    private LocationManager locationManager;
    private LocationListener locationListener;
    private LocationListener continuousLocationListener;
    private Geocoder geocoder;

    @Override
    public void onActivityCreate() {
        super.onActivityCreate();
        initializePlugin();
    }
    
    /**
     * 初始化插件，确保LocationManager可用
     */
    private void initializePlugin() {
        if (locationManager != null && geocoder != null) {
            return; // 已经初始化
        }
        
        Context context = null;
        
        // 尝试多种方式获取Context
        if (mWXSDKInstance != null) {
            context = mWXSDKInstance.getContext();
        }
        
        // 如果第一种方式失败，记录但不尝试其他复杂方法
        if (context == null) {
            Log.w(TAG, "无法从mWXSDKInstance获取Context");
        }
        
        if (context != null) {
            locationManager = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
            geocoder = new Geocoder(context, Locale.getDefault());
            Log.d(TAG, "LocationPlugin 初始化成功: LocationManager=" + (locationManager != null) + ", Geocoder=" + (geocoder != null));
        } else {
            Log.e(TAG, "LocationPlugin 初始化失败: Context为空");
        }
    }

    /**
     * 获取当前位置（同步方法）
     * 使用 @JSMethod 注解 (Weex)
     */
    @JSMethod(uiThread = false)
    public String getLocationSync() {
        JSONObject result = new JSONObject();
        try {
            Log.d(TAG, "getLocationSync 被调用");
            
            Context context = mWXSDKInstance.getContext();
            if (context == null) {
                result.put("success", false);
                result.put("code", -1);
                result.put("error", "上下文未设置");
                String resultString = result.toString();
                Log.d(TAG, "getLocationSync 返回错误字符串: " + resultString);
                return resultString;
            }
            
            if (!checkLocationPermission(context)) {
                result.put("success", false);
                result.put("code", -2);
                result.put("error", "无定位权限");
                String resultString = result.toString();
                Log.d(TAG, "getLocationSync 返回权限错误字符串: " + resultString);
                return resultString;
            }

            if (!isLocationEnabled()) {
                result.put("success", false);
                result.put("code", -3);
                result.put("error", "位置服务未开启");
                String resultString = result.toString();
                Log.d(TAG, "getLocationSync 返回服务错误字符串: " + resultString);
                return resultString;
            }

            // 获取真实位置数据
            Location location = getLastKnownLocation();
            if (location != null) {
                JSONObject data = locationToJSON(location);
                result.put("success", true);
                result.put("code", 0);
                result.put("data", data);
                result.put("message", "✅ 获取位置成功 (缓存位置)");
                result.put("sdk", "Android LocationManager + Geocoder");
                
                Log.d(TAG, "返回缓存位置数据: " + result.toString());
            } else {
                // 没有缓存位置，返回提示
                result.put("success", false);
                result.put("code", -4);
                result.put("error", "暂无缓存位置，请使用异步方法 getLocation() 获取实时位置");
                result.put("message", "建议使用 getLocation() 方法获取实时位置");
                
                Log.d(TAG, "无缓存位置，建议使用异步方法");
            }
            
        } catch (SecurityException e) {
            Log.e(TAG, "安全异常", e);
            try {
                result.put("success", false);
                result.put("code", -5);
                result.put("error", "权限被拒绝: " + e.getMessage());
            } catch (JSONException ignored) {}
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
            try {
                result.put("success", false);
                result.put("code", -6);
                result.put("error", "JSON处理失败: " + e.getMessage());
            } catch (JSONException ignored) {}
        } catch (Exception e) {
            Log.e(TAG, "同步获取位置失败", e);
            try {
                result.put("success", false);
                result.put("code", -7);
                result.put("error", "定位异常: " + e.getMessage());
            } catch (JSONException ignored) {}
        }
        
        String resultString = result.toString();
        Log.d(TAG, "getLocationSync 返回字符串: " + resultString);
        return resultString;
    }

    /**
     * 获取当前位置（异步方法）
     * 使用 JSCallback (Weex)
     */
    @JSMethod(uiThread = true)
    public void getLocation(final JSCallback callback) {
        Log.d(TAG, "getLocation 异步方法被调用");
        
        Context context = mWXSDKInstance.getContext();
        if (context == null) {
            invokeCallback(callback, createErrorResult(-1, "上下文未设置"));
            return;
        }
        
        // 权限检查
        if (!checkLocationPermission(context)) {
            invokeCallback(callback, createErrorResult(-2, "无定位权限"));
            return;
        }

        // 检查GPS是否开启
        if (!isLocationEnabled()) {
            invokeCallback(callback, createErrorResult(-3, "位置服务未开启"));
            return;
        }

        try {
            // 先尝试获取缓存位置
            Location lastLocation = getLastKnownLocation();
            if (lastLocation != null && isLocationFresh(lastLocation)) {
                Log.d(TAG, "使用新鲜的缓存位置");
                JSONObject result = createSuccessResult(locationToJSON(lastLocation));
                try {
                    result.put("message", "✅ 获取位置成功 (缓存位置)");
                    result.put("sdk", "Android LocationManager + Geocoder");
                } catch (JSONException e) {
                    Log.e(TAG, "JSON处理失败", e);
                }
                invokeCallback(callback, result);
                return;
            }

            Log.d(TAG, "缓存位置过期或不存在，请求实时定位");

            // 请求单次定位
            locationListener = new LocationListener() {
                private boolean callbackInvoked = false;

                @Override
                public void onLocationChanged(Location location) {
                    if (!callbackInvoked) {
                        callbackInvoked = true;
                        Log.d(TAG, "位置更新: " + location.getLatitude() + ", " + location.getLongitude());
                        
                        JSONObject locationData = locationToJSON(location);
                        JSONObject result = createSuccessResult(locationData);
                        try {
                            result.put("message", "✅ 获取位置成功 (实时定位)");
                            result.put("sdk", "Android LocationManager + Geocoder");
                        } catch (JSONException e) {
                            Log.e(TAG, "JSON处理失败", e);
                        }
                        
                        invokeCallback(callback, result);
                        stopLocationUpdates();
                        
                        // 异步获取地址信息
                        getAddressFromLocation(location);
                    }
                }

                @Override
                public void onStatusChanged(String provider, int status, Bundle extras) {
                    Log.d(TAG, "位置状态变化: " + provider + " status: " + status);
                }

                @Override
                public void onProviderEnabled(String provider) {
                    Log.d(TAG, "位置提供者启用: " + provider);
                }

                @Override
                public void onProviderDisabled(String provider) {
                    if (!callbackInvoked) {
                        callbackInvoked = true;
                        Log.w(TAG, "位置提供者禁用: " + provider);
                        invokeCallback(callback, createErrorResult(-4, "定位服务已禁用"));
                        stopLocationUpdates();
                    }
                }
            };

            // 同时尝试 GPS 和网络定位
            boolean gpsEnabled = locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER);
            boolean networkEnabled = locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER);

            if (gpsEnabled) {
                Log.d(TAG, "请求 GPS 定位");
                locationManager.requestSingleUpdate(LocationManager.GPS_PROVIDER, locationListener, Looper.getMainLooper());
            }
            
            if (networkEnabled) {
                Log.d(TAG, "请求网络定位");
                locationManager.requestSingleUpdate(LocationManager.NETWORK_PROVIDER, locationListener, Looper.getMainLooper());
            }

            if (!gpsEnabled && !networkEnabled) {
                invokeCallback(callback, createErrorResult(-5, "GPS和网络定位都不可用"));
                return;
            }

            // 30秒超时机制
            new android.os.Handler().postDelayed(() -> {
                if (locationListener != null) {
                    Log.w(TAG, "定位超时");
                    invokeCallback(callback, createErrorResult(-6, "定位超时，请检查GPS信号或网络连接"));
                    stopLocationUpdates();
                }
            }, 30000);

        } catch (SecurityException e) {
            Log.e(TAG, "安全异常", e);
            invokeCallback(callback, createErrorResult(-7, "安全异常: " + e.getMessage()));
        } catch (Exception e) {
            Log.e(TAG, "定位失败", e);
            invokeCallback(callback, createErrorResult(-8, "定位失败: " + e.getMessage()));
        }
    }

    /**
     * 地址反向解析
     */
    @JSMethod(uiThread = true)
    public void reverseGeocode(JSONObject params, final JSCallback callback) {
        if (params == null) {
            invokeCallback(callback, createErrorResult(-1, "参数不能为空"));
            return;
        }

        try {
            double latitude = params.getDouble("latitude");
            double longitude = params.getDouble("longitude");

            if (latitude == 0 && longitude == 0) {
                invokeCallback(callback, createErrorResult(-2, "经纬度参数无效"));
                return;
            }

            Log.d(TAG, "开始地址解析: " + latitude + ", " + longitude);

            // 执行地址解析
            new Thread(() -> {
                try {
                    List<Address> addresses = geocoder.getFromLocation(latitude, longitude, 1);

                    if (addresses != null && addresses.size() > 0) {
                        Address address = addresses.get(0);
                        JSONObject addressData = addressToJSON(address);
                        JSONObject result = createSuccessResult(addressData);
                        invokeCallback(callback, result);
                    } else {
                        invokeCallback(callback, createErrorResult(-3, "无法解析地址信息"));
                    }
                } catch (Exception e) {
                    Log.e(TAG, "地址解析失败", e);
                    invokeCallback(callback, createErrorResult(-4, "地址解析失败: " + e.getMessage()));
                }
            }).start();

        } catch (JSONException e) {
            Log.e(TAG, "地址解析参数错误", e);
            invokeCallback(callback, createErrorResult(-5, "参数解析错误: " + e.getMessage()));
        } catch (Exception e) {
            Log.e(TAG, "地址解析参数错误", e);
            invokeCallback(callback, createErrorResult(-5, "参数解析错误: " + e.getMessage()));
        }
    }

    /**
     * 插件测试方法
     */
    @JSMethod(uiThread = false)
    public String test() {
        Log.d(TAG, "test 方法被调用");
        
        JSONObject result = new JSONObject();
        try {
            Context context = mWXSDKInstance.getContext();
            
            result.put("success", true);
            result.put("code", 0);
            result.put("message", "🎉 插件测试成功！真实定位功能已启用");
            result.put("version", "2.0.0-real-location");
            result.put("timestamp", System.currentTimeMillis());
            result.put("plugin", "LocationPlugin");
            result.put("sdk", "Android LocationManager + Geocoder");
            
            JSONArray features = new JSONArray();
            features.put("GPS实时定位");
            features.put("网络定位");
            features.put("缓存位置检查");
            features.put("地址反向解析");
            features.put("权限状态检查");
            features.put("位置服务状态检查");
            features.put("超时保护机制");
            features.put("异步回调支持");
            result.put("features", features);
            
            // 添加设备状态信息
            JSONObject deviceInfo = new JSONObject();
            if (context != null) {
                deviceInfo.put("hasLocationPermission", checkLocationPermission(context));
                deviceInfo.put("locationServiceEnabled", isLocationEnabled());
                deviceInfo.put("gpsEnabled", locationManager != null && 
                    locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER));
                deviceInfo.put("networkEnabled", locationManager != null && 
                    locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER));
                deviceInfo.put("geocoderAvailable", geocoder != null && Geocoder.isPresent());
            }
            result.put("deviceInfo", deviceInfo);
            
            JSONArray methods = new JSONArray();
            methods.put("getLocationSync() - 获取缓存位置");
            methods.put("getLocation(callback) - 获取实时位置");
            methods.put("getLocationWithAddress(callback) - 获取位置+地址");
            methods.put("reverseGeocode(params, callback) - 地址解析");
            methods.put("checkPermission() - 权限检查");
            methods.put("stopLocationUpdates() - 停止定位");
            result.put("methods", methods);
            
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
        }
        
        String resultString = result.toString();
        Log.d(TAG, "test 方法返回字符串: " + resultString);
        return resultString;
    }

    /**
     * 检查权限状态
     */
    @JSMethod(uiThread = false)
    public String checkPermission() {
        Log.d(TAG, "checkPermission 方法被调用");
        
        JSONObject result = new JSONObject();
        Context context = mWXSDKInstance.getContext();
        
        if (context == null) {
            try {
                result.put("success", false);
                result.put("error", "上下文未设置");
            } catch (JSONException e) {
                Log.e(TAG, "JSON处理失败", e);
            }
            return result.toString();
        }
        
        try {
            int fineLocation = context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION);
            int coarseLocation = context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION);
            
            boolean hasPermission = (fineLocation == android.content.pm.PackageManager.PERMISSION_GRANTED) ||
                                   (coarseLocation == android.content.pm.PackageManager.PERMISSION_GRANTED);
            
            result.put("success", true);
            result.put("hasPermission", hasPermission);
            result.put("fineLocation", fineLocation == android.content.pm.PackageManager.PERMISSION_GRANTED);
            result.put("coarseLocation", coarseLocation == android.content.pm.PackageManager.PERMISSION_GRANTED);
            result.put("locationEnabled", isLocationEnabled());
            
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
            try {
                result.put("success", false);
                result.put("error", "权限检查失败: " + e.getMessage());
            } catch (JSONException ignored) {}
        } catch (Exception e) {
            try {
                result.put("success", false);
                result.put("error", "权限检查失败: " + e.getMessage());
            } catch (JSONException ignored) {}
        }
        
        String resultString = result.toString();
        Log.d(TAG, "checkPermission 方法返回字符串: " + resultString);
        return resultString;
    }

    /**
     * 停止持续定位
     */
    @JSMethod(uiThread = false)
    public String stopLocationUpdates() {
        try {
            if (locationListener != null && locationManager != null) {
                locationManager.removeUpdates(locationListener);
                locationListener = null;
                Log.d(TAG, "停止单次定位监听");
            }
            
            if (continuousLocationListener != null && locationManager != null) {
                locationManager.removeUpdates(continuousLocationListener);
                continuousLocationListener = null;
                Log.d(TAG, "停止持续定位监听");
            }
            
            JSONObject result = new JSONObject();
            result.put("success", true);
            result.put("message", "定位监听已停止");
            String resultString = result.toString();
            Log.d(TAG, "stopLocationUpdates 成功返回字符串: " + resultString);
            return resultString;
            
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
        } catch (Exception e) {
            Log.e(TAG, "停止定位失败", e);
        }
        
        JSONObject errorResult = createErrorResult(-1, "停止定位失败");
        String resultString = errorResult.toString();
        Log.d(TAG, "stopLocationUpdates 返回字符串: " + resultString);
        return resultString;
    }

    /**
     * 异步获取位置地址信息（仅记录日志，不阻塞回调）
     */
    private void getAddressFromLocation(Location location) {
        new Thread(() -> {
            try {
                if (geocoder != null && location != null) {
                    List<Address> addresses = geocoder.getFromLocation(
                        location.getLatitude(), 
                        location.getLongitude(), 
                        1
                    );
                    
                    if (addresses != null && addresses.size() > 0) {
                        Address address = addresses.get(0);
                        String fullAddress = address.getAddressLine(0);
                        String country = address.getCountryName();
                        String city = address.getLocality();
                        
                        Log.d(TAG, "地址解析成功:");
                        Log.d(TAG, "完整地址: " + fullAddress);
                        Log.d(TAG, "国家: " + country);
                        Log.d(TAG, "城市: " + city);
                    } else {
                        Log.w(TAG, "地址解析失败: 无法获取地址信息");
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, "地址解析异常: " + e.getMessage(), e);
            }
        }).start();
    }

    /**
     * 获取位置和地址信息（包含地址解析）
     */
    @JSMethod(uiThread = true)  
    public void getLocationWithAddress(final JSCallback callback) {
        Log.d(TAG, "getLocationWithAddress 被调用");
        
        Context context = mWXSDKInstance.getContext();
        if (context == null) {
            invokeCallback(callback, createErrorResult(-1, "上下文未设置"));
            return;
        }
        
        if (!checkLocationPermission(context)) {
            invokeCallback(callback, createErrorResult(-2, "无定位权限"));
            return;
        }

        if (!isLocationEnabled()) {
            invokeCallback(callback, createErrorResult(-3, "位置服务未开启"));
            return;
        }

        try {
            // 请求位置信息
            locationListener = new LocationListener() {
                private boolean callbackInvoked = false;

                @Override
                public void onLocationChanged(Location location) {
                    if (!callbackInvoked) {
                        callbackInvoked = true;
                        Log.d(TAG, "位置获取成功，开始地址解析");
                        
                        // 先返回位置信息
                        JSONObject locationData = locationToJSON(location);
                        
                        // 异步获取地址信息
                        new Thread(() -> {
                            try {
                                JSONObject finalResult = createSuccessResult(locationData);
                                
                                if (geocoder != null) {
                                    List<Address> addresses = geocoder.getFromLocation(
                                        location.getLatitude(), 
                                        location.getLongitude(), 
                                        1
                                    );
                                    
                                    if (addresses != null && addresses.size() > 0) {
                                        Address address = addresses.get(0);
                                        JSONObject addressData = addressToJSON(address);
                                        
                                        // 合并位置和地址信息
                                        finalResult.put("data", locationData);
                                        finalResult.put("address", addressData);
                                        finalResult.put("message", "✅ 获取位置和地址成功");
                                        
                                        Log.d(TAG, "地址解析完成: " + address.getAddressLine(0));
                                    } else {
                                        finalResult.put("message", "✅ 获取位置成功，地址解析失败");
                                        Log.w(TAG, "地址解析失败");
                                    }
                                } else {
                                    finalResult.put("message", "✅ 获取位置成功，地址解析不可用");
                                }
                                
                                finalResult.put("sdk", "Android LocationManager + Geocoder");
                                invokeCallback(callback, finalResult);
                                
                            } catch (Exception e) {
                                Log.e(TAG, "地址解析异常", e);
                                JSONObject result = createSuccessResult(locationData);
                                try {
                                    result.put("message", "✅ 获取位置成功，地址解析异常: " + e.getMessage());
                                    result.put("sdk", "Android LocationManager + Geocoder");
                                } catch (JSONException ignored) {}
                                invokeCallback(callback, result);
                            }
                        }).start();
                        
                        stopLocationUpdates();
                    }
                }

                @Override
                public void onStatusChanged(String provider, int status, Bundle extras) {
                    Log.d(TAG, "位置状态变化: " + provider + " status: " + status);
                }

                @Override
                public void onProviderEnabled(String provider) {
                    Log.d(TAG, "位置提供者启用: " + provider);
                }

                @Override
                public void onProviderDisabled(String provider) {
                    if (!callbackInvoked) {
                        callbackInvoked = true;
                        Log.w(TAG, "位置提供者禁用: " + provider);
                        invokeCallback(callback, createErrorResult(-4, "定位服务已禁用"));
                        stopLocationUpdates();
                    }
                }
            };

            // 请求位置更新
            String provider = getBestProvider();
            locationManager.requestSingleUpdate(provider, locationListener, Looper.getMainLooper());
            Log.d(TAG, "开始定位和地址解析，使用提供者: " + provider);

            // 30秒超时
            new android.os.Handler().postDelayed(() -> {
                if (locationListener != null) {
                    invokeCallback(callback, createErrorResult(-5, "定位超时"));
                    stopLocationUpdates();
                }
            }, 30000);

        } catch (SecurityException e) {
            Log.e(TAG, "安全异常", e);
            invokeCallback(callback, createErrorResult(-6, "安全异常: " + e.getMessage()));
        } catch (Exception e) {
            Log.e(TAG, "定位失败", e);
            invokeCallback(callback, createErrorResult(-7, "定位失败: " + e.getMessage()));
        }
    }

    // ==================== 辅助方法 ====================

    /**
     * 获取最后已知位置
     */
    private Location getLastKnownLocation() throws SecurityException {
        Location gpsLocation = null;
        Location networkLocation = null;

        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                gpsLocation = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                networkLocation = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
            }
        } catch (Exception e) {
            Log.e(TAG, "获取最后位置失败", e);
        }

        if (gpsLocation == null) {
            return networkLocation;
        }
        if (networkLocation == null) {
            return gpsLocation;
        }

        // 返回更新的位置
        return gpsLocation.getTime() > networkLocation.getTime() ? gpsLocation : networkLocation;
    }

    /**
     * 获取最佳位置提供者
     */
    private String getBestProvider() {
        if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
            return LocationManager.GPS_PROVIDER;
        } else if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
            return LocationManager.NETWORK_PROVIDER;
        } else {
            return LocationManager.PASSIVE_PROVIDER;
        }
    }

    /**
     * 检查定位权限
     */
    private boolean checkLocationPermission(Context context) {
        if (context == null) return false;
        
        int fineLocation = context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION);
        int coarseLocation = context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION);
        
        return fineLocation == android.content.pm.PackageManager.PERMISSION_GRANTED ||
               coarseLocation == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }

    /**
     * 检查位置服务是否启用
     */
    private boolean isLocationEnabled() {
        // 确保插件已初始化
        if (locationManager == null) {
            Log.w(TAG, "LocationManager 为空，尝试重新初始化");
            initializePlugin();
        }
        
        if (locationManager == null) {
            Log.w(TAG, "LocationManager 仍为空，位置服务不可用");
            return false;
        }
        
        // Android P (API 28) 及以上版本
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            try {
                boolean enabled = locationManager.isLocationEnabled();
                Log.d(TAG, "Android P+ API检测: SDK=" + android.os.Build.VERSION.SDK_INT + ", LocationEnabled=" + enabled);
                return enabled;
            } catch (Exception e) {
                Log.w(TAG, "无法获取位置服务状态，使用备用检测", e);
            }
        }
        
        // Android P 以下版本或备用检测
        try {
            boolean gpsEnabled = locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER);
            boolean networkEnabled = locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER);
            boolean enabled = gpsEnabled || networkEnabled;
            
            Log.d(TAG, "传统API检测: SDK=" + android.os.Build.VERSION.SDK_INT + ", GPS=" + gpsEnabled + ", Network=" + networkEnabled + ", Enabled=" + enabled);
            return enabled;
        } catch (Exception e) {
            Log.e(TAG, "位置服务检测失败", e);
            return false;
        }
    }

    /**
     * 检查位置是否新鲜（10分钟内）
     */
    private boolean isLocationFresh(Location location) {
        if (location == null) {
            return false;
        }
        long locationTime = location.getTime();
        long currentTime = System.currentTimeMillis();
        long timeDifference = currentTime - locationTime;
        
        Log.d(TAG, "位置时间差: " + (timeDifference / 1000) + "秒");
        return timeDifference < 600000; // 10分钟
    }

    /**
     * 位置对象转JSONObject
     */
    private JSONObject locationToJSON(Location location) {
        JSONObject data = new JSONObject();
        try {
            data.put("latitude", location.getLatitude());
            data.put("longitude", location.getLongitude());
            data.put("accuracy", location.getAccuracy());
            data.put("altitude", location.getAltitude());
            data.put("speed", location.getSpeed());
            data.put("bearing", location.getBearing());
            data.put("time", location.getTime());
            data.put("provider", location.getProvider());
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
        }
        return data;
    }

    /**
     * 地址对象转JSONObject
     */
    private JSONObject addressToJSON(Address address) {
        JSONObject data = new JSONObject();
        try {
            data.put("country", address.getCountryName() != null ? address.getCountryName() : "");
            data.put("province", address.getAdminArea() != null ? address.getAdminArea() : "");
            data.put("city", address.getLocality() != null ? address.getLocality() : "");
            data.put("district", address.getSubLocality() != null ? address.getSubLocality() : "");
            data.put("street", address.getThoroughfare() != null ? address.getThoroughfare() : "");
            data.put("streetNumber", address.getSubThoroughfare() != null ? address.getSubThoroughfare() : "");
            data.put("postalCode", address.getPostalCode() != null ? address.getPostalCode() : "");
            data.put("formattedAddress", address.getAddressLine(0) != null ? address.getAddressLine(0) : "");
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
        }
        return data;
    }

    /**
     * 创建成功结果
     */
    private JSONObject createSuccessResult(Object data) {
        JSONObject result = new JSONObject();
        try {
            result.put("code", 0);
            result.put("success", true);
            result.put("data", data);
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
        }
        return result;
    }
    
    /**
     * 创建错误结果
     */
    private JSONObject createErrorResult(int code, String error) {
        JSONObject result = new JSONObject();
        try {
            result.put("success", false);
            result.put("code", code);
            result.put("error", error);
        } catch (JSONException e) {
            Log.e(TAG, "JSON处理失败", e);
        }
        return result;
    }
    
    /**
     * 调用回调函数，确保传递字符串
     */
    private void invokeCallback(JSCallback callback, JSONObject result) {
        if (callback != null && result != null) {
            String resultString = result.toString();
            Log.d(TAG, "回调返回字符串: " + resultString);
            callback.invoke(resultString);
        }
    }
}