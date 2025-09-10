#!/usr/bin/env python3
"""
创建测试站点数据
"""

from sqlalchemy.orm import Session
from app.core.database import get_db, engine, Base
from app.models.site import Site
from datetime import datetime

def create_test_sites():
    """创建10个测试站点"""
    print("正在创建测试站点...")
    
    # 确保数据库表存在
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 检查是否已有站点
        existing_sites = db.query(Site).count()
        if existing_sites > 0:
            print(f"ℹ️ 数据库中已有 {existing_sites} 个站点")
            return
        
        # 测试站点数据
        test_sites = [
            {
                "site_name": "北京朝阳基站001",
                "site_code": "BJ-CD-001",
                "site_type": "macro",
                "address": "北京市朝阳区三里屯街道",
                "latitude": 39.936404,
                "longitude": 116.443303,
                "status": "planning",
                "frequency_band": "2.6GHz",
                "technology": "5G",
                "coverage_area": "商业区",
                "power_supply": "市电+备用电池",
                "contact_person": "张工程师",
                "contact_phone": "13800138001"
            },
            {
                "site_name": "上海浦东基站002",
                "site_code": "SH-PD-002", 
                "site_type": "macro",
                "address": "上海市浦东新区陆家嘴金融区",
                "latitude": 31.239668,
                "longitude": 121.499763,
                "status": "construction",
                "frequency_band": "3.5GHz",
                "technology": "5G",
                "coverage_area": "金融区",
                "power_supply": "市电+UPS",
                "contact_person": "李经理",
                "contact_phone": "13900139002"
            },
            {
                "site_name": "深圳南山微基站003",
                "site_code": "SZ-NS-003",
                "site_type": "micro",
                "address": "深圳市南山区科技园",
                "latitude": 22.543527,
                "longitude": 113.944464,
                "status": "construction",
                "frequency_band": "2.1GHz",
                "technology": "4G",
                "coverage_area": "科技园区",
                "power_supply": "PoE供电",
                "contact_person": "王工",
                "contact_phone": "13700137003"
            },
            {
                "site_name": "广州天河室内站004",
                "site_code": "GZ-TH-004",
                "site_type": "indoor",
                "address": "广州市天河区天河城购物中心",
                "latitude": 23.133254,
                "longitude": 113.324573,
                "status": "operational",
                "frequency_band": "1.8GHz",
                "technology": "4G/5G",
                "coverage_area": "商场内部",
                "power_supply": "交流供电",
                "contact_person": "陈主管",
                "contact_phone": "13600136004"
            },
            {
                "site_name": "杭州西湖基站005",
                "site_code": "HZ-XH-005",
                "site_type": "macro",
                "address": "杭州市西湖区西湖景区",
                "latitude": 30.243504,
                "longitude": 120.139403,
                "status": "planning",
                "frequency_band": "700MHz",
                "technology": "5G",
                "coverage_area": "景区",
                "power_supply": "市电+太阳能",
                "contact_person": "刘工程师",
                "contact_phone": "13500135005"
            },
            {
                "site_name": "成都锦江基站006",
                "site_code": "CD-JJ-006",
                "site_type": "macro",
                "address": "成都市锦江区春熙路",
                "latitude": 30.660898,
                "longitude": 104.076475,
                "status": "construction",
                "frequency_band": "2.6GHz",
                "technology": "5G",
                "coverage_area": "商业步行街",
                "power_supply": "市电+备用发电机",
                "contact_person": "赵经理",
                "contact_phone": "13400134006"
            },
            {
                "site_name": "武汉江汉微基站007",
                "site_code": "WH-JH-007",
                "site_type": "micro",
                "address": "武汉市江汉区汉口江滩",
                "latitude": 30.585315,
                "longitude": 114.279467,
                "status": "planning",
                "frequency_band": "3.5GHz",
                "technology": "5G",
                "coverage_area": "江滩公园",
                "power_supply": "市电供电",
                "contact_person": "周工",
                "contact_phone": "13300133007"
            },
            {
                "site_name": "南京鼓楼基站008",
                "site_code": "NJ-GL-008",
                "site_type": "macro",
                "address": "南京市鼓楼区新街口",
                "latitude": 32.046813,
                "longitude": 118.776352,
                "status": "operational",
                "frequency_band": "2.1GHz",
                "technology": "4G",
                "coverage_area": "商业中心",
                "power_supply": "市电+UPS",
                "contact_person": "孙主管",
                "contact_phone": "13200132008"
            },
            {
                "site_name": "西安雁塔基站009",
                "site_code": "XA-YT-009",
                "site_type": "macro",
                "address": "西安市雁塔区大雁塔北广场",
                "latitude": 34.215049,
                "longitude": 108.961256,
                "status": "construction",
                "frequency_band": "2.6GHz",
                "technology": "5G",
                "coverage_area": "旅游景区",
                "power_supply": "市电+备用电池",
                "contact_person": "郑工程师",
                "contact_phone": "13100131009"
            },
            {
                "site_name": "青岛市南基站010",
                "site_code": "QD-SN-010",
                "site_type": "macro",
                "address": "青岛市市南区五四广场",
                "latitude": 36.073611,
                "longitude": 120.389444,
                "status": "planning",
                "frequency_band": "3.5GHz",
                "technology": "5G",
                "coverage_area": "海滨广场",
                "power_supply": "市电+风力发电",
                "contact_person": "吴经理",
                "contact_phone": "13000130010"
            }
        ]
        
        # 创建站点对象
        for site_data in test_sites:
            # 提取城市信息
            city_name = ""
            if "北京" in site_data["address"]:
                city_name = "北京市"
            elif "上海" in site_data["address"]:
                city_name = "上海市"
            elif "深圳" in site_data["address"]:
                city_name = "深圳市"
            elif "广州" in site_data["address"]:
                city_name = "广州市"
            elif "杭州" in site_data["address"]:
                city_name = "杭州市"
            elif "成都" in site_data["address"]:
                city_name = "成都市"
            elif "武汉" in site_data["address"]:
                city_name = "武汉市"
            elif "南京" in site_data["address"]:
                city_name = "南京市"
            elif "西安" in site_data["address"]:
                city_name = "西安市"
            elif "青岛" in site_data["address"]:
                city_name = "青岛市"
            
            site = Site(
                site_name=site_data["site_name"],
                site_code=site_data["site_code"],
                site_type=site_data["site_type"],
                address=site_data["address"],
                latitude=site_data["latitude"],
                longitude=site_data["longitude"],
                city=city_name,
                status=site_data["status"],
                contact_person=site_data["contact_person"],
                contact_phone=site_data["contact_phone"],
                description=f"{site_data['technology']}技术，{site_data['frequency_band']}频段，覆盖{site_data['coverage_area']}，{site_data['power_supply']}"
            )
            db.add(site)
        
        db.commit()
        print("✅ 成功创建10个测试站点:")
        for i, site_data in enumerate(test_sites, 1):
            print(f"   {i}. {site_data['site_name']} ({site_data['site_code']}) - {site_data['status']}")
        
    except Exception as e:
        print(f"❌ 创建站点失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_sites()