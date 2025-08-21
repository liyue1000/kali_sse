"""
访问控制器

实现基于角色的访问控制 (RBAC) 和权限管理。
"""

import logging
from typing import Dict, Any, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class Permission(Enum):
    """权限枚举"""
    EXECUTE_COMMAND = "execute_command"
    VIEW_TASKS = "view_tasks"
    CANCEL_TASKS = "cancel_tasks"
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MODIFY_CONFIGURATION = "modify_configuration"


class Role(Enum):
    """角色枚举"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AccessController:
    """访问控制器"""
    
    def __init__(self):
        """初始化访问控制器"""
        self.role_permissions = self._init_role_permissions()
        self.user_roles: Dict[str, Role] = {}
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        
        logger.info("访问控制器初始化完成")
    
    def _init_role_permissions(self) -> Dict[Role, Set[Permission]]:
        """初始化角色权限映射"""
        return {
            Role.ADMIN: {
                Permission.EXECUTE_COMMAND,
                Permission.VIEW_TASKS,
                Permission.CANCEL_TASKS,
                Permission.MANAGE_USERS,
                Permission.VIEW_AUDIT_LOGS,
                Permission.MODIFY_CONFIGURATION
            },
            Role.OPERATOR: {
                Permission.EXECUTE_COMMAND,
                Permission.VIEW_TASKS,
                Permission.CANCEL_TASKS
            },
            Role.VIEWER: {
                Permission.VIEW_TASKS
            }
        }
    
    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """
        检查用户权限
        
        Args:
            user_id: 用户ID
            permission: 权限
            
        Returns:
            是否有权限
        """
        user_role = self.user_roles.get(user_id)
        if not user_role:
            return False
        
        allowed_permissions = self.role_permissions.get(user_role, set())
        return permission in allowed_permissions
    
    def assign_role(self, user_id: str, role: Role) -> None:
        """
        分配角色
        
        Args:
            user_id: 用户ID
            role: 角色
        """
        self.user_roles[user_id] = role
        logger.info(f"用户 {user_id} 分配角色: {role.value}")
    
    def get_user_role(self, user_id: str) -> Optional[Role]:
        """
        获取用户角色
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户角色
        """
        return self.user_roles.get(user_id)
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        获取用户权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            权限集合
        """
        user_role = self.user_roles.get(user_id)
        if not user_role:
            return set()
        
        return self.role_permissions.get(user_role, set())
