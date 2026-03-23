"""
随机删除权重分析工具
与随机查看权重分析类似，用于分析随机删除算法
"""
import os
import sys
import math
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from models.enhanced_database import EnhancedDatabaseManager


def get_deletion_weights(db_path, top_n=100):
    """
    获取用于删除的权重分析
    """
    if not os.path.exists(db_path):
        print(f"错误：数据库文件不存在 - {db_path}")
        return []
    
    try:
        db_manager = EnhancedDatabaseManager(db_path)
        
        # 获取日记数据
        diaries = db_manager._execute(
            "SELECT * FROM diaries ORDER BY date ASC",
            fetch='all'
        )
        
        if not diaries:
            print("数据库中没有日记数据")
            return []
        
        # 计算每个日记的删除权重
        diary_weights = []
        now = datetime.now()
        
        for diary in diaries:
            # 解析日期
            date = datetime.strptime(diary['date'], "%Y-%m-%d %H:%M:%S")
            
            # 计算距离今天的天数
            days_ago = (now - date).days
            
            # 原始时间权重：时间越久远权重越高
            time_weight_raw = math.log(days_ago + 1)
            
            # 原始查看次数权重：查看次数越多权重越高
            view_count = diary['view_count']
            view_count_weight_raw = math.sqrt(view_count)
            
            diary_weights.append({
                'id': diary['id'],
                'time_weight_raw': time_weight_raw,
                'view_count_weight_raw': view_count_weight_raw,
                'view_count': view_count,
                'days_ago': days_ago
            })
        
        # 使用分位数归一化
        n = len(diary_weights)
        
        # 按时间权重排序，分配分位数
        sorted_by_time = sorted(diary_weights, key=lambda x: x['time_weight_raw'])
        for i, item in enumerate(sorted_by_time):
            item['time_weight_norm'] = i / (n - 1) if n > 1 else 0.5
        
        # 按查看次数权重排序，分配分位数
        sorted_by_view_count = sorted(diary_weights, key=lambda x: x['view_count'])
        for i, item in enumerate(sorted_by_view_count):
            item['view_count_weight_norm'] = i / (n - 1) if n > 1 else 0.5
        
        # 计算最终权重 (随机删除：alpha=0.6, beta=0.4)
        for item in diary_weights:
            alpha = 0.6  # 时间权重系数
            beta = 0.4   # 查看次数权重系数
            item['final_weight'] = alpha * item['time_weight_norm'] + beta * item['view_count_weight_norm']
        
        # 按最终权重降序排列并返回前N个
        sorted_by_final_weight = sorted(diary_weights, key=lambda x: x['final_weight'], reverse=True)
        
        db_manager.close()
        
        return sorted_by_final_weight[:top_n]
    
    except Exception as e:
        print(f"分析数据库时出错: {e}")
        return []


def print_deletion_weights(db_path, top_n=100):
    """
    打印删除权重信息
    """
    results = get_deletion_weights(db_path, top_n)
    
    print(f"前 {len(results)} 个日记的删除权重（按权重降序排列）")
    print(f"{'ID':<10} {'权重':<15} {'查看次数':<10} {'距今天数':<10}")
    print(f"{'-'*50}")
    
    for item in results:
        print(f"{item['id']:<10} {item['final_weight']:<15.6f} {item['view_count']:<10} {item['days_ago']:<10}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='随机删除权重分析工具')
    parser.add_argument('--db', type=str, default="data/diary.db", help='数据库路径 (默认: data/diary.db)')
    parser.add_argument('--top', type=int, default=100, help='显示前N个结果 (默认: 100)')
    
    args = parser.parse_args()
    
    print("随机删除算法 - 权重分析")
    print("="*50)
    
    print_deletion_weights(args.db, args.top)
    
    print("\\n说明：")
    print("- ID: 日记的唯一标识符")
    print("- 权重: 用于删除选择的权重值，数值越大被选中删除概率越高")
    print("- 计算公式: 权重 = 0.6 × 时间权重归一化值 + 0.4 × 查看次数权重归一化值")
    print("- 时间越久远、查看次数越多，被删除概率越大")