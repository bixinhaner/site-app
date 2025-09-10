import math
import aiohttp
import asyncio
from typing import Optional, Tuple

async def reverse_geocode(latitude: float, longitude: float) -> Optional[str]:
    """逆地理编码获取地址"""
    
    # 这里可以使用不同的地图服务API
    # 示例使用高德地图API（需要申请API Key）
    
    # 如果没有配置API，返回简单的坐标描述
    return f"纬度: {latitude:.6f}, 经度: {longitude:.6f}"

def validate_gps_accuracy(accuracy: float, required_accuracy: float = 10.0) -> bool:
    """验证GPS精度是否满足要求"""
    return accuracy <= required_accuracy

def calculate_distance(
    lat1: float, lon1: float, 
    lat2: float, lon2: float
) -> float:
    """计算两个GPS坐标之间的距离（米）"""
    
    # 使用Haversine公式
    R = 6371000  # 地球半径（米）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance

def validate_gps_coordinates(latitude: float, longitude: float) -> bool:
    """验证GPS坐标有效性"""
    return -90 <= latitude <= 90 and -180 <= longitude <= 180

def format_gps_coordinates(latitude: float, longitude: float) -> str:
    """格式化GPS坐标显示"""
    lat_dir = "N" if latitude >= 0 else "S"
    lon_dir = "E" if longitude >= 0 else "W"
    
    return f"{abs(latitude):.6f}°{lat_dir}, {abs(longitude):.6f}°{lon_dir}"

def is_within_site_boundary(
    check_lat: float, check_lon: float,
    site_lat: float, site_lon: float,
    radius: float = 100.0
) -> bool:
    """检查GPS坐标是否在站点范围内"""
    
    distance = calculate_distance(check_lat, check_lon, site_lat, site_lon)
    return distance <= radius

class GPSValidator:
    """GPS验证器"""
    
    def __init__(self, required_accuracy: float = 10.0, site_radius: float = 100.0):
        self.required_accuracy = required_accuracy
        self.site_radius = site_radius
    
    def validate_location(
        self, 
        latitude: float, 
        longitude: float, 
        accuracy: float,
        site_latitude: Optional[float] = None,
        site_longitude: Optional[float] = None
    ) -> dict:
        """综合验证GPS位置"""
        
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # 验证坐标有效性
        if not validate_gps_coordinates(latitude, longitude):
            result["valid"] = False
            result["errors"].append("GPS坐标无效")
        
        # 验证精度
        if accuracy > self.required_accuracy:
            result["warnings"].append(f"GPS精度较低: {accuracy}m (要求: {self.required_accuracy}m)")
        
        # 验证是否在站点范围内
        if site_latitude is not None and site_longitude is not None:
            if not is_within_site_boundary(
                latitude, longitude, 
                site_latitude, site_longitude, 
                self.site_radius
            ):
                result["warnings"].append(f"位置可能不在站点范围内")
        
        return result