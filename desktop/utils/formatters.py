"""
格式化工具模块
提供各类数据格式化功能
"""


def format_tags_html(tags: list) -> str:
    """
    将标签列表格式化为HTML胶囊样式
    
    Args:
        tags: 标签字典列表，每个字典包含 'name' 键
        
    Returns:
        格式化后的HTML字符串
    """
    if not tags:
        return '<span style="color:#999;">无标签</span>'
    
    # 预设配色方案（柔和色调）
    colors = [
        ('#e3f2fd', '#1976d2'),  # 蓝
        ('#f3e5f5', '#7b1fa2'),  # 紫
        ('#e8f5e9', '#388e3c'),  # 绿
        ('#fff3e0', '#f57c00'),  # 橙
        ('#fce4ec', '#c2185b'),  # 粉
        ('#e0f2f1', '#00796b'),  # 青
        ('#f5f5f5', '#616161'),  # 灰
        ('#e8eaf6', '#3f51b5'),  # 靛蓝
    ]
    
    html_parts = []
    for i, tag in enumerate(tags):
        bg_color, text_color = colors[i % len(colors)]
        tag_name = tag["name"] if isinstance(tag, dict) else str(tag)
        tag_html = (f'<span style="background:{bg_color}; color:{text_color}; '
                   f'padding:2px 10px; border-radius:12px; margin-right:6px; '
                   f'font-size:12px; display:inline-block;">{tag_name}</span>')
        html_parts.append(tag_html)
    
    return ''.join(html_parts)
