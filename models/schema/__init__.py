"""
Schema子包 - 数据库Schema初始化模块

包含各功能域的Schema初始化器：
- diary: 日记表
- tag: 标签表
- statistics: 统计表
- fts5: 全文搜索表
- twophase: 两阶段提交协调表

使用工厂模式统一管理初始化流程
"""
from models.schema.factory import SchemaInitializerFactory, SchemaInitializerCoordinator

__all__ = [
    'SchemaInitializerFactory',
    'SchemaInitializerCoordinator',
]
