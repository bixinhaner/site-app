"""
用户日志相关的API端点
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, text
from typing import List, Optional
from datetime import datetime, timedelta
import json

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.user_log import UserLog
from app.schemas.user_log import (
    UserLogCreate, 
    UserLogBatchCreate, 
    UserLogResponse, 
    UserLogFilter,
    UserLogStats,
    UserActivitySummary
)

router = APIRouter()


@router.post("/logs", response_model=dict)
async def create_log(
    log_data: UserLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建单个用户日志"""
    try:
        # 解析时间戳
        log_timestamp = datetime.fromisoformat(log_data.timestamp.replace('Z', '+00:00'))
        
        # 创建日志记录
        log_entry = UserLog.create_from_client_log(
            log_data.dict(),
            user_id=current_user.id,
            username=current_user.username
        )
        log_entry.timestamp = log_timestamp
        
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        
        return {"success": True, "log_id": log_entry.id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建日志失败: {str(e)}"
        )


@router.post("/logs/batch", response_model=dict)
async def create_logs_batch(
    batch_data: UserLogBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量创建用户日志"""
    try:
        created_count = 0
        
        for log_data in batch_data.logs:
            try:
                # 解析时间戳
                log_timestamp = datetime.fromisoformat(log_data.timestamp.replace('Z', '+00:00'))
                
                # 创建日志记录
                log_entry = UserLog.create_from_client_log(
                    log_data.dict(),
                    user_id=current_user.id,
                    username=current_user.username
                )
                log_entry.timestamp = log_timestamp
                
                db.add(log_entry)
                created_count += 1
                
            except Exception as e:
                # 记录错误但继续处理其他日志
                print(f"处理日志时出错: {e}")
                continue
        
        db.commit()
        
        return {
            "success": True,
            "created_count": created_count,
            "total_count": len(batch_data.logs)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量创建日志失败: {str(e)}"
        )


@router.get("/logs", response_model=List[UserLogResponse])
async def get_logs(
    user_id: Optional[int] = Query(None),
    session_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """查询用户日志"""
    
    # 普通用户只能查看自己的日志
    if current_user.role not in ['admin', 'manager']:
        user_id = current_user.id
    
    query = db.query(UserLog)
    
    # 应用过滤条件
    if user_id:
        query = query.filter(UserLog.user_id == user_id)
    if session_id:
        query = query.filter(UserLog.session_id == session_id)
    if action:
        query = query.filter(UserLog.action == action)
    if level:
        query = query.filter(UserLog.level == level)
    if start_time:
        query = query.filter(UserLog.timestamp >= start_time)
    if end_time:
        query = query.filter(UserLog.timestamp <= end_time)
    
    # 排序和分页
    logs = query.order_by(desc(UserLog.timestamp)).offset(offset).limit(limit).all()
    
    return logs


@router.get("/logs/stats", response_model=UserLogStats)
async def get_log_stats(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取日志统计信息（仅管理员）"""
    
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    # 默认查询最近7天的数据
    if not end_time:
        end_time = datetime.now()
    if not start_time:
        start_time = end_time - timedelta(days=7)
    
    query = db.query(UserLog).filter(
        and_(
            UserLog.timestamp >= start_time,
            UserLog.timestamp <= end_time
        )
    )
    
    # 总体统计
    total_logs = query.count()
    total_sessions = query.with_entities(UserLog.session_id).distinct().count()
    total_users = query.with_entities(UserLog.user_id).distinct().count()
    
    # 操作类型统计
    action_stats = db.query(
        UserLog.action,
        func.count(UserLog.id).label('count')
    ).filter(
        and_(
            UserLog.timestamp >= start_time,
            UserLog.timestamp <= end_time
        )
    ).group_by(UserLog.action).all()
    
    action_counts = {action: count for action, count in action_stats}
    
    # 日志级别统计
    level_stats = db.query(
        UserLog.level,
        func.count(UserLog.id).label('count')
    ).filter(
        and_(
            UserLog.timestamp >= start_time,
            UserLog.timestamp <= end_time
        )
    ).group_by(UserLog.level).all()
    
    level_counts = {level: count for level, count in level_stats}
    
    # 每小时活动统计
    hourly_stats = db.query(
        func.extract('hour', UserLog.timestamp).label('hour'),
        func.count(UserLog.id).label('count')
    ).filter(
        and_(
            UserLog.timestamp >= start_time,
            UserLog.timestamp <= end_time
        )
    ).group_by('hour').all()
    
    hourly_activity = {str(int(hour)): count for hour, count in hourly_stats}
    
    # 热门页面统计
    page_stats = db.query(
        UserLog.page_route,
        func.count(UserLog.id).label('count')
    ).filter(
        and_(
            UserLog.timestamp >= start_time,
            UserLog.timestamp <= end_time,
            UserLog.page_route.isnot(None)
        )
    ).group_by(UserLog.page_route).order_by(desc('count')).limit(10).all()
    
    top_pages = [{"page": page, "count": count} for page, count in page_stats]
    
    # 错误摘要
    error_stats = db.query(
        UserLog.error_message,
        func.count(UserLog.id).label('count')
    ).filter(
        and_(
            UserLog.timestamp >= start_time,
            UserLog.timestamp <= end_time,
            UserLog.level == 'ERROR',
            UserLog.error_message.isnot(None)
        )
    ).group_by(UserLog.error_message).order_by(desc('count')).limit(10).all()
    
    error_summary = [{"error": error, "count": count} for error, count in error_stats]
    
    return UserLogStats(
        total_logs=total_logs,
        total_sessions=total_sessions,
        total_users=total_users,
        action_counts=action_counts,
        level_counts=level_counts,
        hourly_activity=hourly_activity,
        top_pages=top_pages,
        error_summary=error_summary
    )


@router.get("/logs/users/{user_id}/activity", response_model=UserActivitySummary)
async def get_user_activity(
    user_id: int,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取特定用户的活动摘要"""
    
    # 权限检查：用户只能查看自己的活动，管理员可以查看所有人的
    if current_user.role not in ['admin', 'manager'] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    # 获取用户信息
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 默认查询最近30天的数据
    if not end_time:
        end_time = datetime.now()
    if not start_time:
        start_time = end_time - timedelta(days=30)
    
    query = db.query(UserLog).filter(
        and_(
            UserLog.user_id == user_id,
            UserLog.timestamp >= start_time,
            UserLog.timestamp <= end_time
        )
    )
    
    # 基本统计
    total_actions = query.count()
    session_count = query.with_entities(UserLog.session_id).distinct().count()
    
    # 时间范围
    first_action_result = query.order_by(UserLog.timestamp).first()
    last_action_result = query.order_by(desc(UserLog.timestamp)).first()
    
    first_action = first_action_result.timestamp if first_action_result else start_time
    last_action = last_action_result.timestamp if last_action_result else start_time
    
    # 热门操作
    action_stats = query.with_entities(
        UserLog.action,
        func.count(UserLog.id).label('count')
    ).group_by(UserLog.action).order_by(desc('count')).limit(10).all()
    
    top_actions = [{"action": action, "count": count} for action, count in action_stats]
    
    # 热门页面
    page_stats = query.filter(UserLog.page_route.isnot(None)).with_entities(
        UserLog.page_route,
        func.count(UserLog.id).label('count')
    ).group_by(UserLog.page_route).order_by(desc('count')).limit(10).all()
    
    most_visited_pages = [{"page": page, "count": count} for page, count in page_stats]
    
    # 错误统计
    error_count = query.filter(UserLog.level == 'ERROR').count()
    
    return UserActivitySummary(
        user_id=user_id,
        username=user.username,
        total_actions=total_actions,
        session_count=session_count,
        first_action=first_action,
        last_action=last_action,
        top_actions=top_actions,
        most_visited_pages=most_visited_pages,
        error_count=error_count
    )


@router.delete("/logs/cleanup")
async def cleanup_old_logs(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清理旧日志（仅管理员）"""
    
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 删除旧日志
    deleted_count = db.query(UserLog).filter(
        UserLog.timestamp < cutoff_date
    ).delete()
    
    db.commit()
    
    return {
        "success": True,
        "deleted_count": deleted_count,
        "cutoff_date": cutoff_date.isoformat()
    }