"""
用户行为日志模型
记录用户在APP中的所有操作行为和使用轨迹
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserLog(Base):
    __tablename__ = "user_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)  # 会话ID
    user_id = Column(Integer, nullable=True, index=True)  # 用户ID (可为空，支持匿名日志)
    username = Column(String(50), nullable=True, index=True)  # 用户名
    
    # 日志基本信息
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)  # 操作类型
    level = Column(String(20), default="INFO", index=True)  # 日志级别: INFO, WARN, ERROR
    
    # 页面信息
    page_route = Column(String(200), nullable=True, index=True)  # 页面路由
    page_options = Column(JSON, nullable=True)  # 页面参数
    
    # 操作数据
    action_data = Column(JSON, nullable=True)  # 操作相关数据
    
    # 设备信息
    device_platform = Column(String(50), nullable=True)  # 设备平台
    device_model = Column(String(100), nullable=True)  # 设备型号
    screen_width = Column(Integer, nullable=True)  # 屏幕宽度
    screen_height = Column(Integer, nullable=True)  # 屏幕高度
    
    # 错误信息 (仅ERROR级别使用)
    error_message = Column(Text, nullable=True)  # 错误消息
    error_stack = Column(Text, nullable=True)  # 错误堆栈
    error_context = Column(JSON, nullable=True)  # 错误上下文
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引优化
    __table_args__ = (
        Index('idx_user_logs_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_user_logs_session_timestamp', 'session_id', 'timestamp'),
        Index('idx_user_logs_action_timestamp', 'action', 'timestamp'),
        Index('idx_user_logs_level_timestamp', 'level', 'timestamp'),
        Index('idx_user_logs_page_timestamp', 'page_route', 'timestamp'),
    )
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'username': self.username,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'action': self.action,
            'level': self.level,
            'page_route': self.page_route,
            'page_options': self.page_options,
            'action_data': self.action_data,
            'device_platform': self.device_platform,
            'device_model': self.device_model,
            'screen_width': self.screen_width,
            'screen_height': self.screen_height,
            'error_message': self.error_message,
            'error_stack': self.error_stack,
            'error_context': self.error_context,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_from_client_log(cls, log_data: dict, user_id: int = None, username: str = None):
        """从客户端日志数据创建日志记录"""
        
        # 提取设备信息
        device_info = log_data.get('deviceInfo', {})
        
        # 提取页面信息
        page_info = log_data.get('page', {})
        
        # 提取用户信息
        user_info = log_data.get('user', {})
        
        # 提取错误信息
        error_info = log_data.get('data', {}).get('error') if log_data.get('level') == 'ERROR' else None
        
        return cls(
            session_id=log_data.get('sessionId'),
            user_id=user_id or user_info.get('userId'),
            username=username or user_info.get('username'),
            timestamp=log_data.get('timestamp'),
            action=log_data.get('action'),
            level=log_data.get('level', 'INFO'),
            page_route=page_info.get('route'),
            page_options=page_info.get('options'),
            action_data=log_data.get('data'),
            device_platform=device_info.get('platform'),
            device_model=device_info.get('model'),
            screen_width=device_info.get('screenWidth'),
            screen_height=device_info.get('screenHeight'),
            error_message=error_info.get('message') if error_info else None,
            error_stack=error_info.get('stack') if error_info else None,
            error_context=log_data.get('data', {}).get('context') if log_data.get('level') == 'ERROR' else None
        )