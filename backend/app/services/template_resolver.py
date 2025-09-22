"""
模板解析服务
提供基于上下文的模板匹配和解析功能
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.inspection import (
    InspectionTemplate, TemplateBinding
)
from app.models.site import Site


class ResolveContext:
    """解析上下文"""
    def __init__(
        self,
        site_id: Optional[int] = None,
        site_type: Optional[str] = None,
        task_id: Optional[str] = None,
        task_type: Optional[str] = None,
        region: Optional[str] = None,
        customer: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        self.site_id = site_id
        self.site_type = site_type
        self.task_id = task_id
        self.task_type = task_type
        self.region = region
        self.customer = customer
        self.tags = tags or []


class TemplateMatchResult:
    """模板匹配结果"""
    def __init__(
        self,
        template_id: str,
        binding_id: int,
        match_score: float,
        priority: int,
        template: InspectionTemplate,
        binding: TemplateBinding,
        explain: str
    ):
        self.template_id = template_id
        self.binding_id = binding_id
        self.match_score = match_score
        self.priority = priority
        self.template = template
        self.binding = binding
        self.explain = explain


class TemplateResolver:
    """模板解析器"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def resolve_template(self, context: ResolveContext) -> Optional[TemplateMatchResult]:
        """
        解析最匹配的模板
        
        Args:
            context: 解析上下文
            
        Returns:
            TemplateMatchResult or None
        """
        # 获取所有活跃的绑定
        now = datetime.utcnow()
        
        bindings_query = self.db.query(TemplateBinding).filter(
            TemplateBinding.active == True
        )
        
        # 时间窗口过滤
        bindings_query = bindings_query.filter(
            or_(
                TemplateBinding.valid_from.is_(None),
                TemplateBinding.valid_from <= now
            ),
            or_(
                TemplateBinding.valid_to.is_(None),
                TemplateBinding.valid_to >= now
            )
        )
        
        bindings = bindings_query.all()
        
        if not bindings:
            return None
        
        # 计算每个绑定的匹配度
        matches = []
        for binding in bindings:
            score = self._calculate_match_score(binding, context)
            if score > 0:  # 只考虑有匹配度的绑定
                matches.append((binding, score))
        
        if not matches:
            return None
        
        # 排序：匹配度 -> priority -> updated_at (降序)
        matches.sort(key=lambda x: (x[1], x[0].priority, x[0].updated_at), reverse=True)
        
        # 取最佳匹配
        best_binding, best_score = matches[0]
        
        # 获取模板信息
        template = self.db.query(InspectionTemplate).filter(
            InspectionTemplate.id == best_binding.template_id
        ).first()
        
        if not template:
            return None
        
        # 生成解释
        explain = self._generate_explain(best_binding, context, best_score)
        
        return TemplateMatchResult(
            template_id=template.id,
            binding_id=best_binding.id,
            match_score=best_score,
            priority=best_binding.priority,
            template=template,
            binding=best_binding,
            explain=explain
        )
    
    def _calculate_match_score(self, binding: TemplateBinding, context: ResolveContext) -> float:
        """
        计算匹配度分数
        
        规则：
        - 完全匹配 site_id（+2）
        - 匹配 site_type（+1）
        - 匹配 task_type（+1）
        - 匹配 region/customer（+0.5 each）
        - tags 至少一个相交（+0.2）
        """
        score = 0.0
        
        # Site ID 匹配（最高优先级）
        if binding.site_id and context.site_id:
            if binding.site_id == context.site_id:
                score += 2.0
            else:
                # Site ID 指定但不匹配，直接返回 0
                return 0.0
        
        # Site Type 匹配
        if binding.site_type and context.site_type:
            if binding.site_type == context.site_type:
                score += 1.0
            else:
                # Site Type 指定但不匹配，直接返回 0
                return 0.0
        
        # Task Type 匹配
        if binding.task_type and context.task_type:
            if binding.task_type.value == context.task_type:
                score += 1.0
            else:
                # Task Type 指定但不匹配，直接返回 0
                return 0.0
        
        # Region 匹配
        if binding.region and context.region:
            if binding.region == context.region:
                score += 0.5
            else:
                return 0.0
        
        # Customer 匹配
        if binding.customer and context.customer:
            if binding.customer == context.customer:
                score += 0.5
            else:
                return 0.0
        
        # Tags 匹配（至少一个相交）
        if binding.tags and context.tags:
            binding_tags = set(binding.tags) if isinstance(binding.tags, list) else set()
            context_tags = set(context.tags)
            if binding_tags.intersection(context_tags):
                score += 0.2
        
        # 如果没有任何条件匹配，但也没有冲突条件，给予基础分数
        if score == 0.0:
            # 检查是否是完全通用的绑定（所有条件都为空）
            if (not binding.site_id and not binding.site_type and 
                not binding.task_type and not binding.region and 
                not binding.customer and not binding.tags):
                score = 0.1  # 通用匹配的基础分数
        
        return score
    
    def _generate_explain(self, binding: TemplateBinding, context: ResolveContext, score: float) -> str:
        """生成匹配解释"""
        explanations = []
        
        if binding.site_id and context.site_id and binding.site_id == context.site_id:
            explanations.append(f"精确匹配站点ID {binding.site_id}")
        
        if binding.site_type and context.site_type and binding.site_type == context.site_type:
            explanations.append(f"匹配站点类型 '{binding.site_type}'")
        
        if binding.task_type and context.task_type and binding.task_type.value == context.task_type:
            explanations.append(f"匹配任务类型 '{binding.task_type.value}'")
        
        if binding.region and context.region and binding.region == context.region:
            explanations.append(f"匹配区域 '{binding.region}'")
        
        if binding.customer and context.customer and binding.customer == context.customer:
            explanations.append(f"匹配客户 '{binding.customer}'")
        
        if binding.tags and context.tags:
            binding_tags = set(binding.tags) if isinstance(binding.tags, list) else set()
            context_tags = set(context.tags)
            common_tags = binding_tags.intersection(context_tags)
            if common_tags:
                explanations.append(f"标签匹配 {list(common_tags)}")
        
        if not explanations:
            explanations.append("通用模板匹配")
        
        explain = "; ".join(explanations)
        explain += f" (匹配度: {score:.1f}, 优先级: {binding.priority})"
        
        if binding.notes:
            explain += f" - {binding.notes}"
        
        return explain
    
    def get_matching_bindings(self, context: ResolveContext) -> List[TemplateMatchResult]:
        """
        获取所有匹配的绑定（用于调试和测试）
        
        Returns:
            排序后的匹配结果列表
        """
        # 获取所有活跃的绑定
        now = datetime.utcnow()
        
        bindings_query = self.db.query(TemplateBinding).filter(
            TemplateBinding.active == True
        )
        
        # 时间窗口过滤
        bindings_query = bindings_query.filter(
            or_(
                TemplateBinding.valid_from.is_(None),
                TemplateBinding.valid_from <= now
            ),
            or_(
                TemplateBinding.valid_to.is_(None),
                TemplateBinding.valid_to >= now
            )
        )
        
        bindings = bindings_query.all()
        
        # 计算每个绑定的匹配度
        results = []
        for binding in bindings:
            score = self._calculate_match_score(binding, context)
            if score > 0:  # 只考虑有匹配度的绑定
                template = self.db.query(InspectionTemplate).filter(
                    InspectionTemplate.id == binding.template_id
                ).first()
                
                if template:
                    explain = self._generate_explain(binding, context, score)
                    results.append(TemplateMatchResult(
                        template_id=template.id,
                        binding_id=binding.id,
                        match_score=score,
                        priority=binding.priority,
                        template=template,
                        binding=binding,
                        explain=explain
                    ))
        
        # 排序：匹配度 -> priority -> updated_at (降序)
        results.sort(key=lambda x: (x.match_score, x.priority, x.binding.updated_at), reverse=True)
        
        return results
    
    def validate_binding_conditions(self, binding_data: Dict[str, Any]) -> List[str]:
        """
        验证绑定条件的有效性
        
        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []
        
        # 验证 site_id 存在性
        if binding_data.get('site_id'):
            site = self.db.query(Site).filter(Site.id == binding_data['site_id']).first()
            if not site:
                errors.append(f"站点 ID {binding_data['site_id']} 不存在")
        
        # 验证 site_type
        if binding_data.get('site_type'):
            valid_site_types = ['macro', 'micro', 'indoor', 'outdoor']
            if binding_data['site_type'] not in valid_site_types:
                errors.append(f"站点类型 '{binding_data['site_type']}' 无效。有效值: {valid_site_types}")
        
        # 验证 priority 范围
        if 'priority' in binding_data:
            priority = binding_data['priority']
            if not isinstance(priority, int) or priority < 1 or priority > 100:
                errors.append("优先级必须是 1-100 之间的整数")
        
        # 验证 tags 格式
        if binding_data.get('tags'):
            tags = binding_data['tags']
            if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                errors.append("标签必须是字符串数组")
        
        # 验证时间窗口
        if binding_data.get('valid_from') and binding_data.get('valid_to'):
            try:
                valid_from = datetime.fromisoformat(binding_data['valid_from'].replace('Z', '+00:00')) if isinstance(binding_data['valid_from'], str) else binding_data['valid_from']
                valid_to = datetime.fromisoformat(binding_data['valid_to'].replace('Z', '+00:00')) if isinstance(binding_data['valid_to'], str) else binding_data['valid_to']
                
                if valid_from >= valid_to:
                    errors.append("生效时间必须早于失效时间")
            except (ValueError, AttributeError):
                errors.append("时间格式错误")
        
        return errors


def create_resolver(db: Session) -> TemplateResolver:
    """创建模板解析器实例"""
    return TemplateResolver(db)