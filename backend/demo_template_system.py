"""
可定制检查模板系统演示脚本

展示模板绑定系统的核心功能：
1. 创建模板和绑定规则
2. 演示不同场景下的模板解析
3. 展示优先级和匹配逻辑
"""

import asyncio
import uuid
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.site import Site
from app.models.inspection import (
    InspectionTemplate, TemplateBinding, TaskTypeEnum
)
from app.services.template_resolver import (
    TemplateResolver, ResolveContext, create_resolver
)


def create_demo_templates(db: Session, user_id: int):
    """创建演示模板"""
    templates = []
    
    # 模板 A: 开站检查模板
    template_a = InspectionTemplate(
        id=str(uuid.uuid4()),
        template_name="5G基站开站检查模板",
        template_data={
            "description": "5G基站设备安装和开站检查",
            "check_categories": [
                {
                    "category_id": "basic_info",
                    "category_name": "基本信息检查",
                    "description": "站点基本信息核实",
                    "sector_specific": False,
                    "items": [
                        {
                            "item_id": "tower_id",
                            "item_name": "铁塔编号确认",
                            "description": "核实并拍照记录铁塔编号",
                            "required_type": "photo",
                            "assigned_role": "inspector",
                            "status": "pending"
                        },
                        {
                            "item_id": "site_coordinates",
                            "item_name": "站点坐标确认",
                            "description": "使用GPS确认站点实际坐标",
                            "required_type": "data",
                            "assigned_role": "inspector",
                            "status": "pending"
                        }
                    ]
                },
                {
                    "category_id": "equipment_check",
                    "category_name": "设备检查",
                    "description": "基站设备状态检查",
                    "sector_specific": True,
                    "items": [
                        {
                            "item_id": "antenna_installation",
                            "item_name": "天线安装检查",
                            "description": "检查天线安装情况、方向角和下倾角",
                            "required_type": "both",
                            "assigned_role": "inspector",
                            "status": "pending"
                        },
                        {
                            "item_id": "power_check",
                            "item_name": "功率参数检查",
                            "description": "测量并记录发射功率参数",
                            "required_type": "data",
                            "assigned_role": "inspector",
                            "status": "pending"
                        }
                    ]
                }
            ]
        },
        created_by=user_id
    )
    
    # 模板 B: 维护检查模板
    template_b = InspectionTemplate(
        id=str(uuid.uuid4()),
        template_name="基站维护检查模板",
        template_data={
            "description": "基站设备维护和例行检查",
            "check_categories": [
                {
                    "category_id": "maintenance_check",
                    "category_name": "维护检查",
                    "description": "设备维护状况检查",
                    "sector_specific": False,
                    "items": [
                        {
                            "item_id": "equipment_status",
                            "item_name": "设备状态检查",
                            "description": "检查设备运行状态和告警信息",
                            "required_type": "both",
                            "assigned_role": "inspector",
                            "status": "pending"
                        },
                        {
                            "item_id": "environmental_check",
                            "item_name": "环境检查",
                            "description": "检查机房温度、湿度和清洁状况",
                            "required_type": "photo",
                            "assigned_role": "inspector",
                            "status": "pending"
                        }
                    ]
                }
            ]
        },
        created_by=user_id
    )
    
    # 模板 C: 应急检修模板
    template_c = InspectionTemplate(
        id=str(uuid.uuid4()),
        template_name="应急检修检查模板",
        template_data={
            "description": "故障应急检修和排查",
            "check_categories": [
                {
                    "category_id": "emergency_check",
                    "category_name": "应急检修",
                    "description": "故障排查和应急处理",
                    "sector_specific": False,
                    "items": [
                        {
                            "item_id": "fault_diagnosis",
                            "item_name": "故障诊断",
                            "description": "分析故障现象和可能原因",
                            "required_type": "both",
                            "assigned_role": "inspector",
                            "status": "pending"
                        }
                    ]
                }
            ]
        },
        created_by=user_id
    )
    
    templates = [template_a, template_b, template_c]
    
    for template in templates:
        db.add(template)
    
    db.commit()
    
    for template in templates:
        db.refresh(template)
    
    return templates


def create_demo_bindings(db: Session, templates, user_id: int):
    """创建演示绑定规则"""
    bindings = []
    
    # 策略 1: VIP站点专属绑定（最高优先级）
    bindings.append(TemplateBinding(
        template_id=templates[0].id,
        site_id=1001,  # 假设1001是VIP站点
        priority=95,
        active=True,
        notes="VIP站点专属开站检查模板",
        created_by=user_id
    ))
    
    # 策略 2: 开站任务 + 宏站类型（高优先级）
    bindings.append(TemplateBinding(
        template_id=templates[0].id,
        site_type="macro",
        task_type=TaskTypeEnum.OPENING_INSPECTION,
        priority=80,
        active=True,
        notes="宏站开站检查标准模板",
        created_by=user_id
    ))
    
    # 策略 3: 开站任务 + 微站类型（中高优先级）
    bindings.append(TemplateBinding(
        template_id=templates[0].id,
        site_type="micro",
        task_type=TaskTypeEnum.OPENING_INSPECTION,
        priority=75,
        active=True,
        notes="微站开站检查简化模板",
        created_by=user_id
    ))
    
    # 策略 4: 维护任务绑定（中优先级）
    bindings.append(TemplateBinding(
        template_id=templates[1].id,
        task_type=TaskTypeEnum.MAINTENANCE,
        priority=60,
        active=True,
        notes="维护任务通用模板",
        created_by=user_id
    ))
    
    # 策略 5: 应急任务绑定（中优先级，多任务类型）
    for task_type in [TaskTypeEnum.POWER_ISSUE, TaskTypeEnum.TRANSMISSION_ISSUE, 
                      TaskTypeEnum.GPS_ISSUE, TaskTypeEnum.SIGNAL_ISSUE]:
        bindings.append(TemplateBinding(
            template_id=templates[2].id,
            task_type=task_type,
            priority=70,
            active=True,
            notes=f"应急检修模板 - {task_type.value}",
            created_by=user_id
        ))
    
    # 策略 6: 区域专属绑定（低优先级）
    bindings.append(TemplateBinding(
        template_id=templates[1].id,
        region="北京",
        priority=40,
        active=True,
        notes="北京区域专用维护模板",
        created_by=user_id
    ))
    
    # 策略 7: 客户专属绑定（低优先级）
    bindings.append(TemplateBinding(
        template_id=templates[1].id,
        customer="中国移动",
        priority=35,
        active=True,
        notes="中国移动客户专用模板",
        created_by=user_id
    ))
    
    # 策略 8: 标签绑定（特殊情况）
    bindings.append(TemplateBinding(
        template_id=templates[0].id,
        tags=["5G", "试点"],
        priority=85,
        active=True,
        notes="5G试点项目专用模板",
        created_by=user_id
    ))
    
    # 策略 9: 时间限制绑定（临时活动）
    bindings.append(TemplateBinding(
        template_id=templates[2].id,
        tags=["春节保障"],
        priority=90,
        active=True,
        valid_from=datetime.utcnow() - timedelta(days=1),
        valid_to=datetime.utcnow() + timedelta(days=30),
        notes="春节保障期间专用应急模板",
        created_by=user_id
    ))
    
    # 策略 10: 通用兜底绑定（最低优先级）
    bindings.append(TemplateBinding(
        template_id=templates[1].id,
        priority=10,
        active=True,
        notes="通用兜底检查模板",
        created_by=user_id
    ))
    
    for binding in bindings:
        db.add(binding)
    
    db.commit()
    
    for binding in bindings:
        db.refresh(binding)
    
    return bindings


def demo_resolver_scenarios(resolver: TemplateResolver):
    """演示不同场景下的模板解析"""
    
    print("=" * 80)
    print("检查模板解析系统演示")
    print("=" * 80)
    
    scenarios = [
        {
            "name": "场景1: VIP站点开站检查",
            "context": ResolveContext(
                site_id=1001,
                site_type="macro", 
                task_type="opening_inspection"
            ),
            "expected": "应该匹配VIP站点专属模板（最高优先级）"
        },
        
        {
            "name": "场景2: 普通宏站开站检查", 
            "context": ResolveContext(
                site_id=2001,
                site_type="macro",
                task_type="opening_inspection"
            ),
            "expected": "应该匹配宏站开站检查标准模板"
        },
        
        {
            "name": "场景3: 微站开站检查",
            "context": ResolveContext(
                site_type="micro",
                task_type="opening_inspection"
            ),
            "expected": "应该匹配微站开站检查简化模板"
        },
        
        {
            "name": "场景4: 5G试点项目开站",
            "context": ResolveContext(
                site_type="macro",
                task_type="opening_inspection",
                tags=["5G", "试点", "重要"]
            ),
            "expected": "应该匹配5G试点项目专用模板（标签优先）"
        },
        
        {
            "name": "场景5: 维护任务",
            "context": ResolveContext(
                site_type="macro",
                task_type="maintenance"
            ),
            "expected": "应该匹配维护任务通用模板"
        },
        
        {
            "name": "场景6: 北京区域维护",
            "context": ResolveContext(
                region="北京",
                task_type="maintenance"
            ),
            "expected": "应该匹配维护任务模板（任务类型优先于区域）"
        },
        
        {
            "name": "场景7: 移动客户维护（仅客户信息）",
            "context": ResolveContext(
                customer="中国移动"
            ),
            "expected": "应该匹配客户专用模板"
        },
        
        {
            "name": "场景8: 断电故障应急检修",
            "context": ResolveContext(
                task_type="power_issue"
            ),
            "expected": "应该匹配应急检修模板"
        },
        
        {
            "name": "场景9: 春节保障应急",
            "context": ResolveContext(
                task_type="signal_issue",
                tags=["春节保障"]
            ),
            "expected": "应该匹配春节保障期间专用应急模板"
        },
        
        {
            "name": "场景10: 无匹配条件（兜底测试）",
            "context": ResolveContext(
                site_type="unknown"
            ),
            "expected": "应该匹配通用兜底模板"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{scenario['name']}")
        print(f"预期: {scenario['expected']}")
        print("-" * 50)
        
        # 执行解析
        result = resolver.resolve_template(scenario['context'])
        
        if result:
            print(f"✅ 匹配成功:")
            print(f"   模板: {result.template.template_name}")
            print(f"   匹配度: {result.match_score:.1f}")
            print(f"   优先级: {result.priority}")
            print(f"   解释: {result.explain}")
            
            # 显示模板内容摘要
            categories = result.template.template_data.get('check_categories', [])
            total_items = sum(len(cat.get('items', [])) for cat in categories)
            print(f"   包含: {len(categories)} 个分类, {total_items} 个检查项")
        else:
            print("❌ 未找到匹配的模板")
        
        # 显示所有匹配结果
        all_matches = resolver.get_matching_bindings(scenario['context'])
        if len(all_matches) > 1:
            print(f"   其他匹配 ({len(all_matches)-1} 个):")
            for match in all_matches[1:4]:  # 显示前3个备选
                print(f"     - {match.template.template_name} "
                      f"(匹配度: {match.match_score:.1f}, 优先级: {match.priority})")


def main():
    """主函数"""
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 查找测试用户（假设存在admin用户）
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            print("错误: 未找到admin用户，请先运行初始化脚本")
            return
        
        print("正在创建演示数据...")
        
        # 创建演示模板
        templates = create_demo_templates(db, admin_user.id)
        print(f"✅ 已创建 {len(templates)} 个演示模板")
        
        # 创建绑定规则
        bindings = create_demo_bindings(db, templates, admin_user.id)
        print(f"✅ 已创建 {len(bindings)} 个绑定规则")
        
        # 创建解析器
        resolver = create_resolver(db)
        
        # 运行演示场景
        demo_resolver_scenarios(resolver)
        
        print("\n" + "=" * 80)
        print("演示完成!")
        print("=" * 80)
        
        # 显示API使用说明
        print("\n📋 API使用说明:")
        print("1. 获取模板列表: GET /api/inspections/templates")
        print("2. 创建模板: POST /api/inspections/templates")
        print("3. 管理绑定: GET/POST/PUT/DELETE /api/inspections/templates/{id}/bindings")
        print("4. 解析模板: POST /api/inspections/templates/resolve")
        print("5. Web管理界面: http://localhost:3000/inspections/templates")
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()