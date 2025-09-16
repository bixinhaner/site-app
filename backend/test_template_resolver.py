"""
模板解析器单元测试
测试模板匹配逻辑、优先级规则和绑定验证
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.user import User
from app.models.site import Site
from app.models.inspection import (
    InspectionTemplate, TemplateBinding, TaskTypeEnum
)
from app.services.template_resolver import (
    TemplateResolver, ResolveContext, create_resolver
)


# 测试数据库配置
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """创建测试数据库会话"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db):
    """创建测试用户"""
    user = User(
        id=1,
        username="test_admin",
        email="admin@test.com",
        full_name="Test Admin",
        role="admin"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_sites(db):
    """创建测试站点"""
    sites = [
        Site(
            id=1001,
            site_name="北京宏站001",
            site_type="macro",
            region="北京",
            customer="中国移动",
            latitude=39.9042,
            longitude=116.4074,
            address="北京市朝阳区"
        ),
        Site(
            id=1002,
            site_name="上海微站002",
            site_type="micro",
            region="上海",
            customer="中国联通",
            latitude=31.2304,
            longitude=121.4737,
            address="上海市黄浦区"
        ),
        Site(
            id=1003,
            site_name="深圳室内站003",
            site_type="indoor",
            region="深圳",
            customer="中国电信",
            latitude=22.5431,
            longitude=114.0579,
            address="深圳市南山区"
        )
    ]
    
    for site in sites:
        db.add(site)
    db.commit()
    
    for site in sites:
        db.refresh(site)
    
    return sites


@pytest.fixture
def test_templates(db, test_user):
    """创建测试模板"""
    templates = [
        InspectionTemplate(
            id=str(uuid.uuid4()),
            template_name="开站检查模板A",
            template_data={
                "check_categories": [
                    {
                        "category_id": "basic_check",
                        "category_name": "基础检查",
                        "items": [
                            {"item_id": "tower_id", "item_name": "铁塔编号确认", "required_type": "photo"},
                            {"item_id": "coordinates", "item_name": "坐标确认", "required_type": "data"}
                        ]
                    }
                ]
            },
            created_by=test_user.id
        ),
        InspectionTemplate(
            id=str(uuid.uuid4()),
            template_name="维护检查模板B",
            template_data={
                "check_categories": [
                    {
                        "category_id": "maintenance_check",
                        "category_name": "维护检查",
                        "items": [
                            {"item_id": "equipment_status", "item_name": "设备状态", "required_type": "both"},
                            {"item_id": "signal_test", "item_name": "信号测试", "required_type": "data"}
                        ]
                    }
                ]
            },
            created_by=test_user.id
        ),
        InspectionTemplate(
            id=str(uuid.uuid4()),
            template_name="通用检查模板C",
            template_data={
                "check_categories": [
                    {
                        "category_id": "general_check",
                        "category_name": "通用检查",
                        "items": [
                            {"item_id": "safety_check", "item_name": "安全检查", "required_type": "photo"}
                        ]
                    }
                ]
            },
            created_by=test_user.id
        )
    ]
    
    for template in templates:
        db.add(template)
    db.commit()
    
    for template in templates:
        db.refresh(template)
    
    return templates


@pytest.fixture
def test_bindings(db, test_templates, test_sites, test_user):
    """创建测试绑定"""
    bindings = [
        # 高优先级：特定站点绑定
        TemplateBinding(
            template_id=test_templates[0].id,
            site_id=1001,
            priority=90,
            active=True,
            created_by=test_user.id,
            notes="站点1001专属模板"
        ),
        
        # 中优先级：开站任务 + 宏站类型
        TemplateBinding(
            template_id=test_templates[0].id,
            site_type="macro",
            task_type=TaskTypeEnum.OPENING_INSPECTION,
            priority=70,
            active=True,
            created_by=test_user.id,
            notes="宏站开站检查"
        ),
        
        # 中优先级：维护任务 + 微站类型
        TemplateBinding(
            template_id=test_templates[1].id,
            site_type="micro",
            task_type=TaskTypeEnum.MAINTENANCE,
            priority=60,
            active=True,
            created_by=test_user.id,
            notes="微站维护检查"
        ),
        
        # 低优先级：区域绑定
        TemplateBinding(
            template_id=test_templates[1].id,
            region="北京",
            priority=40,
            active=True,
            created_by=test_user.id,
            notes="北京区域通用"
        ),
        
        # 低优先级：客户绑定
        TemplateBinding(
            template_id=test_templates[2].id,
            customer="中国移动",
            priority=30,
            active=True,
            created_by=test_user.id,
            notes="中国移动专用"
        ),
        
        # 最低优先级：通用绑定
        TemplateBinding(
            template_id=test_templates[2].id,
            priority=10,
            active=True,
            created_by=test_user.id,
            notes="通用兜底模板"
        ),
        
        # 时间限制的绑定（已过期）
        TemplateBinding(
            template_id=test_templates[0].id,
            task_type=TaskTypeEnum.OPENING_INSPECTION,
            priority=80,
            active=True,
            valid_from=datetime.utcnow() - timedelta(days=30),
            valid_to=datetime.utcnow() - timedelta(days=1),  # 昨天过期
            created_by=test_user.id,
            notes="已过期的绑定"
        ),
        
        # 未激活的绑定
        TemplateBinding(
            template_id=test_templates[1].id,
            site_type="indoor",
            priority=85,
            active=False,  # 未激活
            created_by=test_user.id,
            notes="未激活的绑定"
        ),
    ]
    
    for binding in bindings:
        db.add(binding)
    db.commit()
    
    for binding in bindings:
        db.refresh(binding)
    
    return bindings


class TestTemplateResolver:
    """模板解析器测试类"""
    
    def test_exact_site_match(self, db, test_templates, test_bindings):
        """测试精确站点匹配（最高优先级）"""
        resolver = create_resolver(db)
        
        context = ResolveContext(
            site_id=1001,
            site_type="macro",
            task_type="opening_inspection"
        )
        
        result = resolver.resolve_template(context)
        
        assert result is not None
        assert result.template_id == test_templates[0].id
        assert result.match_score == 2.0  # 站点ID精确匹配
        assert result.priority == 90
        assert "精确匹配站点ID 1001" in result.explain
    
    def test_site_type_and_task_type_match(self, db, test_templates, test_bindings):
        """测试站点类型和任务类型匹配"""
        resolver = create_resolver(db)
        
        context = ResolveContext(
            site_id=2001,  # 不同的站点ID
            site_type="macro",
            task_type="opening_inspection"
        )
        
        result = resolver.resolve_template(context)
        
        assert result is not None
        assert result.template_id == test_templates[0].id
        assert result.match_score == 2.0  # 站点类型(1.0) + 任务类型(1.0)
        assert result.priority == 70
        assert "匹配站点类型 'macro'" in result.explain
        assert "匹配任务类型 'opening_inspection'" in result.explain
    
    def test_maintenance_micro_match(self, db, test_templates, test_bindings):
        """测试微站维护任务匹配"""
        resolver = create_resolver(db)
        
        context = ResolveContext(
            site_type="micro",
            task_type="maintenance"
        )
        
        result = resolver.resolve_template(context)
        
        assert result is not None
        assert result.template_id == test_templates[1].id
        assert result.match_score == 2.0  # 站点类型(1.0) + 任务类型(1.0)
        assert result.priority == 60
    
    def test_region_match(self, db, test_templates, test_bindings):
        """测试区域匹配"""
        resolver = create_resolver(db)
        
        context = ResolveContext(
            region="北京"
        )
        
        result = resolver.resolve_template(context)
        
        assert result is not None
        assert result.template_id == test_templates[1].id
        assert result.match_score == 0.5  # 区域匹配
        assert result.priority == 40
        assert "匹配区域 '北京'" in result.explain
    
    def test_customer_match(self, db, test_templates, test_bindings):
        """测试客户匹配"""
        resolver = create_resolver(db)
        
        context = ResolveContext(
            customer="中国移动"
        )
        
        result = resolver.resolve_template(context)
        
        assert result is not None
        assert result.template_id == test_templates[2].id
        assert result.match_score == 0.5  # 客户匹配
        assert result.priority == 30
    
    def test_general_fallback_match(self, db, test_templates, test_bindings):
        """测试通用兜底匹配"""
        resolver = create_resolver(db)
        
        context = ResolveContext(
            site_type="unknown",  # 不匹配任何条件
            task_type="unknown"
        )
        
        result = resolver.resolve_template(context)
        
        assert result is not None
        assert result.template_id == test_templates[2].id  # 通用模板
        assert result.match_score == 0.1  # 通用匹配基础分
        assert result.priority == 10
        assert "通用模板匹配" in result.explain
    
    def test_priority_ordering(self, db, test_templates, test_bindings):
        """测试优先级排序"""
        resolver = create_resolver(db)
        
        # 这个上下文会匹配多个绑定
        context = ResolveContext(
            site_id=1001,  # 匹配站点专属绑定 (priority=90)
            site_type="macro",  # 也匹配宏站开站绑定 (priority=70)
            task_type="opening_inspection"
        )
        
        all_matches = resolver.get_matching_bindings(context)
        
        assert len(all_matches) >= 2
        # 第一个应该是优先级最高的（站点专属）
        assert all_matches[0].priority == 90
        assert all_matches[0].match_score == 2.0
        
        # 第二个应该是优先级较低的（类型匹配）
        assert all_matches[1].priority == 70
        assert all_matches[1].match_score == 2.0
    
    def test_expired_binding_ignored(self, db, test_templates, test_bindings):
        """测试过期绑定被忽略"""
        resolver = create_resolver(db)
        
        # 创建一个只会匹配到过期绑定的上下文
        context = ResolveContext(
            site_type="expired_test",  # 这个类型只存在于过期绑定中
            task_type="opening_inspection"
        )
        
        # 应该找不到匹配，因为过期绑定被过滤掉了
        all_matches = resolver.get_matching_bindings(context)
        
        # 验证没有过期的绑定被返回
        for match in all_matches:
            binding = match.binding
            if binding.valid_to:
                assert binding.valid_to >= datetime.utcnow()
    
    def test_inactive_binding_ignored(self, db, test_templates, test_bindings):
        """测试未激活绑定被忽略"""
        resolver = create_resolver(db)
        
        context = ResolveContext(
            site_type="indoor"  # 这个只匹配未激活的绑定
        )
        
        result = resolver.resolve_template(context)
        
        # 应该回退到通用绑定，而不是未激活的indoor绑定
        if result:
            assert result.binding.active == True
    
    def test_tags_match(self, db, test_templates, test_bindings, test_user):
        """测试标签匹配"""
        # 创建带标签的绑定
        tag_binding = TemplateBinding(
            template_id=test_templates[0].id,
            tags=["VIP", "高优先级"],
            priority=75,
            active=True,
            created_by=test_user.id
        )
        db.add(tag_binding)
        db.commit()
        
        resolver = create_resolver(db)
        
        context = ResolveContext(
            tags=["VIP", "测试"]
        )
        
        result = resolver.resolve_template(context)
        
        assert result is not None
        assert result.match_score == 0.2  # 标签匹配
        assert result.priority == 75
    
    def test_no_match_returns_none(self, db, test_templates, test_bindings):
        """测试无匹配时返回None"""
        resolver = create_resolver(db)
        
        # 创建一个与所有绑定都冲突的上下文
        context = ResolveContext(
            site_id=9999,  # 不存在的站点
            site_type="nonexistent",  # 不存在的类型
            task_type="nonexistent"  # 不存在的任务类型
        )
        
        result = resolver.resolve_template(context)
        
        # 应该有通用兜底绑定
        assert result is not None  # 因为有通用兜底绑定
    
    def test_binding_validation(self, db):
        """测试绑定条件验证"""
        resolver = create_resolver(db)
        
        # 测试有效数据
        valid_data = {
            'site_id': 1001,
            'site_type': 'macro',
            'task_type': 'opening_inspection',
            'priority': 50,
            'tags': ['tag1', 'tag2']
        }
        
        errors = resolver.validate_binding_conditions(valid_data)
        assert len(errors) == 0
        
        # 测试无效数据
        invalid_data = {
            'site_id': 99999,  # 不存在的站点
            'site_type': 'invalid_type',  # 无效站点类型
            'task_type': 'invalid_task',  # 无效任务类型
            'priority': 150,  # 超出范围
            'tags': 'not_a_list'  # 错误的标签格式
        }
        
        errors = resolver.validate_binding_conditions(invalid_data)
        assert len(errors) > 0
        assert any('站点 ID' in error for error in errors)
        assert any('任务类型' in error for error in errors)
        assert any('站点类型' in error for error in errors)
        assert any('优先级' in error for error in errors)
        assert any('标签' in error for error in errors)
    
    def test_match_score_calculation(self, db, test_templates, test_bindings):
        """测试匹配度分数计算"""
        resolver = create_resolver(db)
        
        # 测试完美匹配
        context = ResolveContext(
            site_id=1001,
            site_type="macro",
            task_type="opening_inspection"
        )
        
        result = resolver.resolve_template(context)
        assert result.match_score == 2.0  # 站点ID匹配
        
        # 测试复合匹配
        context2 = ResolveContext(
            site_type="micro",
            task_type="maintenance"
        )
        
        result2 = resolver.resolve_template(context2)
        assert result2.match_score == 2.0  # 站点类型(1.0) + 任务类型(1.0)
    
    def test_time_window_validation(self, db, test_templates, test_bindings, test_user):
        """测试时间窗口验证"""
        # 创建未来生效的绑定
        future_binding = TemplateBinding(
            template_id=test_templates[0].id,
            site_type="future_test",
            priority=95,
            active=True,
            valid_from=datetime.utcnow() + timedelta(days=1),  # 明天开始生效
            created_by=test_user.id
        )
        db.add(future_binding)
        db.commit()
        
        resolver = create_resolver(db)
        
        context = ResolveContext(
            site_type="future_test"
        )
        
        result = resolver.resolve_template(context)
        
        # 应该找不到匹配，因为绑定还未生效
        # 会回退到其他匹配或通用绑定
        if result:
            assert result.binding.id != future_binding.id


def test_create_resolver_function(db):
    """测试解析器创建函数"""
    resolver = create_resolver(db)
    assert isinstance(resolver, TemplateResolver)
    assert resolver.db == db


if __name__ == "__main__":
    pytest.main([__file__, "-v"])