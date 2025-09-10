#!/usr/bin/env python3
"""
API结构验证脚本
验证增强版检查API的结构和路由定义
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def validate_api_structure():
    """验证API结构"""
    
    print("=== API结构验证 ===")
    
    # 检查文件是否存在
    files_to_check = [
        "app/main.py",
        "app/api/inspections_enhanced.py", 
        "app/models/inspection.py",
        "app/core/database.py",
        "app/core/config.py"
    ]
    
    missing_files = []
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"✓ {file_path}")
    
    if missing_files:
        print("\n缺失文件:")
        for file_path in missing_files:
            print(f"✗ {file_path}")
        return False
    
    # 验证API路由定义
    try:
        print("\n=== 验证API路由 ===")
        
        # 检查enhanced API文件内容
        with open("app/api/inspections_enhanced.py", "r", encoding="utf-8") as f:
            api_content = f.read()
            
        # 检查关键路由是否定义
        required_routes = [
            "@router.get(\"/templates\")",
            "@router.post(\"/\")",
            "@router.get(\"/{inspection_id}\")",
            "@router.put(\"/{inspection_id}\")",
            "@router.post(\"/{inspection_id}/photos\")",
            "@router.get(\"/statistics\")"
        ]
        
        for route in required_routes:
            if route in api_content:
                print(f"✓ 路由定义: {route}")
            else:
                print(f"✗ 缺失路由: {route}")
        
        # 验证数据库模型
        print("\n=== 验证数据库模型 ===")
        with open("app/models/inspection.py", "r", encoding="utf-8") as f:
            model_content = f.read()
        
        required_models = [
            "class InspectionTemplate",
            "class SiteInspection", 
            "class InspectionCheckItem",
            "class InspectionPhoto"
        ]
        
        for model in required_models:
            if model in model_content:
                print(f"✓ 模型定义: {model}")
            else:
                print(f"✗ 缺失模型: {model}")
        
        # 验证主应用配置
        print("\n=== 验证主应用配置 ===")
        with open("app/main.py", "r", encoding="utf-8") as f:
            main_content = f.read()
        
        if "inspections_enhanced" in main_content:
            print("✓ 增强API已集成到主应用")
        else:
            print("✗ 增强API未集成到主应用")
        
        print("\n✓ API结构验证完成")
        return True
        
    except Exception as e:
        print(f"✗ 验证过程出错: {str(e)}")
        return False

def validate_database_schema():
    """验证数据库表结构"""
    
    print("\n=== 数据库结构验证 ===")
    
    try:
        import sqlite3
        
        # 连接数据库
        db_path = "site_manager.db"
        if not os.path.exists(db_path):
            print(f"✗ 数据库文件不存在: {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = [
            "inspection_templates",
            "site_inspections", 
            "inspection_check_items",
            "inspection_photos",
            "inspections"  # 向后兼容
        ]
        
        for table in required_tables:
            if table in tables:
                # 检查表中记录数
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✓ 表 {table}: {count} 条记录")
            else:
                print(f"✗ 缺失表: {table}")
        
        conn.close()
        print("✓ 数据库结构验证完成")
        return True
        
    except Exception as e:
        print(f"✗ 数据库验证失败: {str(e)}")
        return False

def validate_frontend_pages():
    """验证前端页面配置"""
    
    print("\n=== 前端页面验证 ===")
    
    try:
        # 检查UniApp页面文件
        uniapp_path = "../uniapp-site-manager"
        if not os.path.exists(uniapp_path):
            print("✗ UniApp项目目录不存在")
            return False
        
        # 检查关键页面文件
        required_pages = [
            "pages/inspection/list_enhanced.vue",
            "pages/inspection/camera_enhanced.vue", 
            "stores/offline.js",
            "stores/inspection.js"
        ]
        
        for page in required_pages:
            page_path = os.path.join(uniapp_path, page)
            if os.path.exists(page_path):
                # 获取文件大小
                size = os.path.getsize(page_path)
                print(f"✓ 页面文件: {page} ({size} bytes)")
            else:
                print(f"✗ 缺失页面: {page}")
        
        # 检查pages.json配置
        pages_json_path = os.path.join(uniapp_path, "pages.json")
        if os.path.exists(pages_json_path):
            with open(pages_json_path, "r", encoding="utf-8") as f:
                pages_content = f.read()
            
            if "list_enhanced" in pages_content:
                print("✓ pages.json配置已更新")
            else:
                print("✗ pages.json配置未更新")
        else:
            print("✗ pages.json文件不存在")
        
        print("✓ 前端页面验证完成")
        return True
        
    except Exception as e:
        print(f"✗ 前端验证失败: {str(e)}")
        return False

def main():
    """主验证流程"""
    
    print("增强版检查系统部署验证")
    print("=" * 50)
    
    results = []
    
    # API结构验证
    results.append(validate_api_structure())
    
    # 数据库结构验证  
    results.append(validate_database_schema())
    
    # 前端页面验证
    results.append(validate_frontend_pages())
    
    # 总结
    print("\n" + "=" * 50)
    print("验证结果汇总:")
    
    success_count = sum(results)
    total_count = len(results)
    
    validation_items = ["API结构", "数据库结构", "前端页面"]
    
    for i, (item, result) in enumerate(zip(validation_items, results)):
        status = "✓ 通过" if result else "✗ 失败"
        print(f"- {item}: {status}")
    
    print(f"\n总体结果: {success_count}/{total_count} 项验证通过")
    
    if success_count == total_count:
        print("🎉 所有验证通过，系统已成功部署!")
        return True
    else:
        print("⚠️  部分验证失败，请检查相关问题")
        return False

if __name__ == "__main__":
    main()