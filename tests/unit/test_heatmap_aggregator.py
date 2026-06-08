"""
热力图数据聚合方法 + widget 单月视图测试

覆盖 services/statistics_service.py 中：
- get_diary_date_range
- get_diary_counts_by_date_range

以及 views/components/heatmap_panel.py 中：
- 单月 sizeHint 不变量
- 自适应 stride 上限
- 点击幂等性
- 月份导航（切月/上一月/下一月/今天）
"""
from datetime import datetime, timedelta

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDate

from services.statistics_service import StatisticsService


# ============================================================================
# StatisticsService 边界测试
# ============================================================================

class TestGetDiaryDateRange:
    """get_diary_date_range 边界测试"""

    def test_empty_db_returns_none_tuple(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        assert service.get_diary_date_range() == (None, None)

    def test_single_diary_returns_same_date(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        initialized_temp_db._execute(
            "INSERT INTO diaries (date, content) VALUES (?, ?)",
            ('2024-06-15 10:00:00', 'A')
        )
        assert service.get_diary_date_range() == ('2024-06-15', '2024-06-15')

    def test_multi_diary_returns_extremes(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        for day in ('2024-01-01 08:00:00', '2024-06-15 12:00:00', '2024-12-31 23:59:59'):
            initialized_temp_db._execute(
                "INSERT INTO diaries (date, content) VALUES (?, ?)",
                (day, f'content of {day}')
            )
        assert service.get_diary_date_range() == ('2024-01-01', '2024-12-31')

    def test_diary_with_midnight_timestamp(self, initialized_temp_db):
        """00:00:00 时间戳应被正确归到当天"""
        service = StatisticsService(initialized_temp_db)
        initialized_temp_db._execute(
            "INSERT INTO diaries (date, content) VALUES (?, ?)",
            ('2024-03-10 00:00:00', 'midnight')
        )
        assert service.get_diary_date_range() == ('2024-03-10', '2024-03-10')


class TestGetDiaryCountsByDateRange:
    """get_diary_counts_by_date_range 测试"""

    def test_empty_db_returns_empty_dict(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        assert service.get_diary_counts_by_date_range('2024-01-01', '2024-12-31') == {}

    def test_single_day_multiple_entries_aggregated(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        for hour in (8, 12, 18):
            initialized_temp_db._execute(
                "INSERT INTO diaries (date, content) VALUES (?, ?)",
                (f'2024-06-15 {hour:02d}:00:00', f'h{hour}')
            )
        result = service.get_diary_counts_by_date_range('2024-06-01', '2024-06-30')
        assert result == {'2024-06-15': 3}

    def test_range_boundary_inclusive(self, initialized_temp_db):
        """端点日期应被包含"""
        service = StatisticsService(initialized_temp_db)
        for day in ('2024-01-01 09:00:00', '2024-01-31 18:00:00'):
            initialized_temp_db._execute(
                "INSERT INTO diaries (date, content) VALUES (?, ?)",
                (day, day)
            )
        result = service.get_diary_counts_by_date_range('2024-01-01', '2024-01-31')
        assert set(result.keys()) == {'2024-01-01', '2024-01-31'}

    def test_out_of_range_excluded(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        for day in ('2023-12-31 09:00:00', '2024-01-15 09:00:00', '2024-02-01 09:00:00'):
            initialized_temp_db._execute(
                "INSERT INTO diaries (date, content) VALUES (?, ?)",
                (day, day)
            )
        result = service.get_diary_counts_by_date_range('2024-01-01', '2024-01-31')
        assert result == {'2024-01-15': 1}

    def test_no_data_in_range_returns_empty(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        initialized_temp_db._execute(
            "INSERT INTO diaries (date, content) VALUES (?, ?)",
            ('2024-06-15 10:00:00', 'A')
        )
        result = service.get_diary_counts_by_date_range('2025-01-01', '2025-12-31')
        assert result == {}

    def test_empty_start_or_end_returns_empty(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        initialized_temp_db._execute(
            "INSERT INTO diaries (date, content) VALUES (?, ?)",
            ('2024-06-15 10:00:00', 'A')
        )
        assert service.get_diary_counts_by_date_range(None, '2024-12-31') == {}
        assert service.get_diary_counts_by_date_range('2024-01-01', None) == {}
        assert service.get_diary_counts_by_date_range('', '') == {}

    def test_multi_day_distribution(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        samples = [
            ('2024-06-15 09:00:00', 'a1'),
            ('2024-06-15 18:00:00', 'a2'),
            ('2024-06-16 09:00:00', 'b1'),
            ('2024-06-17 09:00:00', 'c1'),
            ('2024-06-17 12:00:00', 'c2'),
            ('2024-06-17 15:00:00', 'c3'),
            ('2024-06-17 21:00:00', 'c4'),
        ]
        for d, c in samples:
            initialized_temp_db._execute(
                "INSERT INTO diaries (date, content) VALUES (?, ?)", (d, c)
            )
        result = service.get_diary_counts_by_date_range('2024-06-15', '2024-06-17')
        assert result == {
            '2024-06-15': 2,
            '2024-06-16': 1,
            '2024-06-17': 4,
        }

    def test_result_keys_are_strings(self, initialized_temp_db):
        service = StatisticsService(initialized_temp_db)
        initialized_temp_db._execute(
            "INSERT INTO diaries (date, content) VALUES (?, ?)",
            ('2024-06-15 10:00:00', 'A')
        )
        result = service.get_diary_counts_by_date_range('2024-06-01', '2024-06-30')
        (key,) = result.keys()
        assert isinstance(key, str)
        assert key == '2024-06-15'

    def test_combined_with_date_range(self, initialized_temp_db):
        """与 get_diary_date_range 联用：找出边界后逐日聚合"""
        service = StatisticsService(initialized_temp_db)
        base = datetime(2024, 3, 10, 10, 0, 0)
        for offset in (0, 1, 5, 10, 20):
            ts = (base + timedelta(days=offset)).strftime('%Y-%m-%d %H:%M:%S')
            initialized_temp_db._execute(
                "INSERT INTO diaries (date, content) VALUES (?, ?)", (ts, str(offset))
            )
        bounds = service.get_diary_date_range()
        assert bounds == ('2024-03-10', '2024-03-30')
        counts = service.get_diary_counts_by_date_range(bounds[0], bounds[1])
        assert sum(counts.values()) == 5
        assert len(counts) == 5


# ============================================================================
# HeatmapCalendarWidget 单月视图
# ============================================================================

class TestHeatmapWidgetSizeHint:
    """回归测试：热力图 sizeHint 高度与宽度必须能容纳当月（4-6 行 × 7 列）"""

    def _make_widget(self, counts, year, month, qapp, adaptive=False):
        from views.components.heatmap_panel import HeatmapCalendarWidget
        w = HeatmapCalendarWidget()
        w.set_adaptive_size(adaptive)
        w.set_data(counts)
        w.set_current_month(year, month)
        return w

    def test_four_week_month_size(self, qapp):
        """4 周月：height = TOP(20) + 2*PAD(12) + 4*STRIDE(14) = 88；width = 2*PAD + 7*STRIDE = 110"""
        # 2027-02: Feb 1 是周一，Feb 28 是周日，恰好 4 周
        w = self._make_widget({'2027-02-15': 1}, 2027, 2, qapp)
        assert w._weeks == 4
        sh = w.sizeHint()
        assert sh.height() == 88, f"4 周月 height 应为 88, 实际 {sh.height()}"
        assert sh.width() == 110, f"4 周月 width 应为 110, 实际 {sh.width()}"

    def test_six_week_month_size(self, qapp):
        """6 周月：height = TOP(20) + 2*PAD(12) + 6*STRIDE(14) = 116；width 不变"""
        # 2026-08: Aug 1 是周六，Aug 31 是周一，需要 6 周
        w = self._make_widget({}, 2026, 8, qapp)
        assert w._weeks == 6
        sh = w.sizeHint()
        assert sh.height() == 116, f"6 周月 height 应为 116, 实际 {sh.height()}"
        assert sh.width() == 110, f"6 周月 width 仍应为 110, 实际 {sh.width()}"

    def test_width_independent_of_weeks(self, qapp):
        """宽度只跟 7 列有关，不同月 width 应一致"""
        w4 = self._make_widget({}, 2027, 2, qapp)
        w5 = self._make_widget({}, 2025, 5, qapp)
        w6 = self._make_widget({}, 2026, 8, qapp)
        assert w4._weeks == 4
        assert w5._weeks == 5
        assert w6._weeks == 6
        w4w = w4.sizeHint().width()
        w5w = w5.sizeHint().width()
        w6w = w6.sizeHint().width()
        assert w4w == w5w == w6w == 110, (
            f"width 应一致，实际 {w4w}/{w5w}/{w6w}"
        )

    def test_clickable_region_covers_all_rows(self, qapp):
        """所有行格子的 y 坐标必须全部落在 widget 高度内"""
        # 6 周月（覆盖范围最广）
        w = self._make_widget({}, 2026, 8, qapp)
        h = w.sizeHint().height()
        for week_idx in range(w._weeks):
            y = w.TOP_LABEL_HEIGHT + w.OUTER_PADDING + week_idx * w.STRIDE
            assert y + w.CELL_SIZE <= h, (
                f"week {week_idx} 底部 y={y + w.CELL_SIZE} 超出 widget 高度 {h}"
            )


class TestHeatmapAdaptiveSize:
    """自适应尺寸测试：set_adaptive_size(True) 后 cell 随宽度变化"""

    def _make_widget(self, counts, year, month, qapp, adaptive=True):
        from views.components.heatmap_panel import HeatmapCalendarWidget
        w = HeatmapCalendarWidget()
        w.set_adaptive_size(adaptive)
        w.set_data(counts)
        w.set_current_month(year, month)
        w.resize(240, 200)
        w.show()
        qapp.processEvents()
        return w

    def test_one_month_adaptive_stride_clamped(self, qapp):
        """单月 6 周：stride 应按 7 列等分，clamp 到 [12, 35]（与 QCalendarWidget 280px 下 35px 列宽对齐）"""
        # 2026-08: 6 周
        w = self._make_widget(
            {'2026-08-15': 1, '2026-08-20': 2},
            2026, 8, qapp,
        )
        assert w._weeks == 6
        assert 12 <= w._stride <= 35, f"stride {w._stride} 不在 [12, 35] 区间"

    def test_short_month_adaptive_stride_within_range(self, qapp):
        """4 周月：stride 应在 [12, 35] 区间"""
        # 2027-02: 4 周
        w = self._make_widget({'2027-02-10': 1}, 2027, 2, qapp)
        assert w._weeks == 4
        assert 12 <= w._stride <= 35, f"stride {w._stride} 越界"

    def test_click_uses_instance_stride_not_class_constant(self, qapp):
        """回归测试：_cell_from_pos 必须用 self._stride，不能用 STRIDE 类常量"""
        from views.components.heatmap_panel import _snap_to_monday

        w = self._make_widget(
            {'2026-08-15': 1, '2026-08-20': 2},
            2026, 8, qapp, adaptive=True,
        )
        # Mon-first：grid_start = Jul 27（Aug 1 周一前最近的一天）
        gs = _snap_to_monday(QDate(2026, 8, 1))
        target = QDate(2026, 8, 15)
        diff = gs.daysTo(target)
        row, col = diff // 7, diff % 7  # row=周序号，col=星期（0=Mon..6=Sun）
        x = w.OUTER_PADDING + col * w._stride + 1
        y = w.TOP_LABEL_HEIGHT + w.OUTER_PADDING + row * w._stride + 1
        result = w._cell_from_pos(x, y)
        assert result is not None, "click should map to a valid date"
        assert result.toString("yyyy-MM-dd") == '2026-08-15', (
            f"click at ({x},{y}) mapped to {result.toString('yyyy-MM-dd')}, "
            f"expected 2026-08-15 — _cell_from_pos 仍在用类常量 STRIDE"
        )

    def test_repeated_click_on_same_cell_is_idempotent(self, qapp):
        """同一格反复点击必须每次都返回同一日期（信号不丢、不偏移）"""
        from PyQt6.QtCore import QEvent, QPointF, Qt
        from PyQt6.QtGui import QMouseEvent
        from views.components.heatmap_panel import _snap_to_monday

        captured = []
        from views.components.heatmap_panel import HeatmapPanelFactory
        panel = HeatmapPanelFactory.create_heatmap_panel(
            None, on_date_clicked=captured.append,
        )
        panel.resize(260, 400)
        panel.show()
        qapp.processEvents()
        w = panel._heatmap
        w.set_data({'2026-08-15': 1})
        w.set_current_month(2026, 8)
        qapp.processEvents()

        gs = _snap_to_monday(QDate.fromString('2026-08-01', 'yyyy-MM-dd'))
        target = QDate.fromString('2026-08-15', 'yyyy-MM-dd')
        diff = gs.daysTo(target)
        row, col = diff // 7, diff % 7
        x = w.OUTER_PADDING + col * w._stride + 1
        y = w.TOP_LABEL_HEIGHT + w.OUTER_PADDING + row * w._stride + 1

        for _ in range(5):
            QApplication.sendEvent(w, QMouseEvent(
                QEvent.Type.MouseButtonPress, QPointF(x, y),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ))
            QApplication.sendEvent(w, QMouseEvent(
                QEvent.Type.MouseButtonRelease, QPointF(x, y),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ))

        assert len(captured) == 5, f"expected 5 clicks, got {len(captured)}"
        assert all(c == '2026-08-15' for c in captured), (
            f"clicks not idempotent: {captured}"
        )


class TestHeatmapMonthNavigation:
    """月份导航测试：切月/上一月/下一月/今天"""

    def test_set_current_month_changes_weeks(self, qapp):
        """不同月份 _weeks 应不同（4-5-6 都有可能）"""
        from views.components.heatmap_panel import HeatmapCalendarWidget
        w = HeatmapCalendarWidget()
        w.set_data({})
        w.set_current_month(2027, 2)  # 4 周（Feb 1 Mon - Feb 28 Sun 紧贴）
        assert w._weeks == 4
        w.set_current_month(2026, 8)  # 6 周（Aug 1 Sat - Aug 31 Mon 跨 6 周）
        assert w._weeks == 6

    def test_current_month_roundtrip(self, qapp):
        """set_current_month 后 current_month() 应能读回"""
        from views.components.heatmap_panel import HeatmapCalendarWidget
        w = HeatmapCalendarWidget()
        w.set_data({})
        w.set_current_month(2025, 7)
        m = w.current_month()
        assert m is not None
        assert m.year() == 2025 and m.month() == 7 and m.day() == 1

    def test_prev_button_fires_callback_with_previous_month(self, qapp):
        """点 ‹ 按钮：on_month_changed 回调收到上一月"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        captured = []
        panel = HeatmapPanelFactory.create_heatmap_panel(
            None, on_month_changed=lambda y, m: captured.append((y, m)),
        )
        panel.show()
        qapp.processEvents()
        panel.set_month(2026, 6)
        qapp.processEvents()
        captured.clear()  # 忽略 set_month 触发的回调

        panel._btn_prev.click()
        qapp.processEvents()
        assert captured == [(2026, 5)], f"prev button should fire (2026, 5), got {captured}"

    def test_next_button_fires_callback_with_next_month(self, qapp):
        """点 › 按钮：on_month_changed 回调收到下一月（跨年）"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        captured = []
        panel = HeatmapPanelFactory.create_heatmap_panel(
            None, on_month_changed=lambda y, m: captured.append((y, m)),
        )
        panel.show()
        qapp.processEvents()
        panel.set_month(2026, 12)
        qapp.processEvents()
        captured.clear()

        panel._btn_next.click()
        qapp.processEvents()
        assert captured == [(2027, 1)], f"next button should fire (2027, 1), got {captured}"

    def test_today_button_jumps_to_current_month(self, qapp):
        """点 [今天]：跳到系统当前月"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        captured = []
        panel = HeatmapPanelFactory.create_heatmap_panel(
            None, on_month_changed=lambda y, m: captured.append((y, m)),
        )
        panel.show()
        qapp.processEvents()
        # 先切到远古月份
        panel.set_month(2020, 1)
        qapp.processEvents()
        captured.clear()

        panel._btn_today.click()
        qapp.processEvents()
        assert len(captured) == 1
        t = QDate.currentDate()
        assert captured[0] == (t.year(), t.month()), (
            f"today button should jump to current month, got {captured[0]}"
        )

    def test_today_button_disabled_when_already_on_today(self, qapp):
        """已在当月时，今天按钮应被禁用（避免无意义回调）"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        panel = HeatmapPanelFactory.create_heatmap_panel(None)
        panel.show()
        qapp.processEvents()
        t = QDate.currentDate()
        panel.set_month(t.year(), t.month())
        qapp.processEvents()
        assert not panel._btn_today.isEnabled(), (
            "今天按钮在当月时应被禁用"
        )

    def test_today_button_enabled_on_other_months(self, qapp):
        """不在当月时，今天按钮应可用"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        panel = HeatmapPanelFactory.create_heatmap_panel(None)
        panel.show()
        qapp.processEvents()
        t = QDate.currentDate()
        # 切到去年的同月，肯定不是当月
        panel.set_month(t.year() - 1, t.month())
        qapp.processEvents()
        assert panel._btn_today.isEnabled(), (
            "今天按钮不在当月时应可用"
        )

    def test_panel_exposes_set_month_helper(self, qapp):
        """panel.set_month 外部入口可正常工作"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        panel = HeatmapPanelFactory.create_heatmap_panel(None)
        panel.set_month(2025, 3)
        m = panel._heatmap.current_month()
        assert m is not None and m.year() == 2025 and m.month() == 3


class TestHeatmapFactoryStructure:
    """工厂结构：导航按钮 / 滚动容器 / 月份标签"""

    def test_factory_creates_nav_buttons(self, qapp):
        """工厂应创建 prev/next/today 三个按钮"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        panel = HeatmapPanelFactory.create_heatmap_panel(None)
        assert hasattr(panel, '_btn_prev')
        assert hasattr(panel, '_btn_next')
        assert hasattr(panel, '_btn_today')

    def test_factory_creates_month_label(self, qapp):
        """工厂应创建月份标签"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        panel = HeatmapPanelFactory.create_heatmap_panel(None)
        assert hasattr(panel, '_month_label')

    def test_factory_wraps_heatmap_in_scroll_area(self, qapp):
        """工厂用 QScrollArea 包热力图（即使单月通常不需要滚动）"""
        from views.components.heatmap_panel import HeatmapPanelFactory
        panel = HeatmapPanelFactory.create_heatmap_panel(None)
        assert hasattr(panel, '_scroll')
        # 默认开启自适应
        assert panel._heatmap._adaptive_size is True
