# -*- coding: utf-8 -*-
"""主窗口：统一游戏列表、搜索、筛选、启动游戏。"""
import os
import subprocess

from PyQt5.QtCore import Qt, QSize, QTimer, QPoint, QRect, QEvent
from PyQt5.QtGui import QIcon, QFont, QColor, QKeySequence, QPainter, QFontMetrics
from PyQt5.QtWidgets import (
    QMainWindow, QTableWidget, QTableWidgetItem, QHeaderView, QToolBar, QAction,
    QMessageBox, QLineEdit, QAbstractItemView, QApplication, QStyle, QToolButton,
    QStyledItemDelegate, QMenu, QWidget, QHBoxLayout, QLabel, QPushButton,
    QStyleOptionViewItem,
)

from config import AppConfig, icon_path, APP_DIR
from game_list import scan_games
from settings_dialog import ImportSettingsDialog
from ui_scale import get_scale

UI_FONT = "Microsoft YaHei UI"


class NoFocusDelegate(QStyledItemDelegate):
    """不绘制单元格焦点框：选中时只高亮整行，无虚线方框。"""

    def drawFocus(self, painter, option, rect):
        pass  # 故意不绘制焦点框

    def paint(self, painter, option, index):
        # 清除焦点状态，避免当前单元格出现虚线焦点矩形
        option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)


class EmulatorTagButton(QPushButton):
    """药丸形彩色标签按钮，用于模拟器列展示（类似多维表格的彩色标签）。

    纯背景填充、无边框线、大圆角药丸形、浅色底+深色字。
    颜色按预设色板分配，同一行内的同名模拟器颜色一致。
    """

    # 预设色板：每项 = (浅背景, 深文字, hover深背景)
    PALETTE = [
        ("#fce8e6", "#c5221f", "#f4cccc"),  # 红
        ("#e6f4ea", "#188038", "#d0e8d6"),  # 绿
        ("#e8f0fe", "#1a73e8", "#d2e3fc"),  # 蓝
        ("#fce4ec", "#c2185b", "#f8bbd0"),  # 粉
        ("#f3e8fd", "#8430ce", "#e1c6f5"),  # 紫
        ("#e0f7fa", "#006064", "#b8eef2"),  # 青
        ("#fef7e0", "#b06000", "#fce8b3"),  # 橙
        ("#fffbe6", "#8d6e00", "#ffefb3"),  # 黄
        ("#eef2ff", "#3949ab", "#d5dcff"),  # 靛蓝
        ("#e6f4f1", "#00796b", "#b8e0d8"),  # 青绿
    ]

    def __init__(self, text, parent=None, context_cb=None, color_index=0):
        super().__init__(text, parent)
        self.setFlat(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        bg, fg, hover_bg = self.PALETTE[color_index % len(self.PALETTE)]
        # 多维表格风格：纯填充、无边框、药丸形大圆角
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background: {bg}; color: {fg}; border: none;"
            f"  border-radius: 10px; padding: 2px 10px; font-size: 11px;"
            f"}}"
            f"QPushButton:hover {{ background: {hover_bg}; }}"
            f"QPushButton:pressed {{ background: {fg}; color: white; }}"
        )
        self._context_cb = context_cb

    def contextMenuEvent(self, event):
        # 转发右键到表格的上下文菜单，避免标签按钮吞掉右键事件
        if self._context_cb:
            self._context_cb(event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)


def _hash_color_index(name: str) -> int:
    """按模拟器名生成稳定的基础颜色索引（同名模拟器基础色一致）。
    使用 FNV-1a 哈希，对短词也能较好分散。
    """
    h = 2166136261
    for ch in name:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def _dedup_emulators(emulators):
    """按名称去重，返回 [(name, path), ...]（保留第一个）。"""
    pairs = []
    seen = set()
    for emu in emulators:
        name = emu.name or os.path.basename(emu.path) or "模拟器"
        if name in seen:
            continue
        seen.add(name)
        pairs.append((name, emu.path))
    return pairs


def _tag_color_indices(names):
    """给同一行的标签分配颜色索引。

    先按名称哈希取色（同名颜色稳定），若本行内有其他标签撞色则顺延到
    下一个未使用的颜色，避免几个模拟器标签全是同一种蓝色。
    """
    count = len(EmulatorTagButton.PALETTE)
    used = set()
    indices = []
    for name in names:
        idx = _hash_color_index(name) % count
        if idx in used:
            for step in range(1, count):
                candidate = (idx + step) % count
                if candidate not in used:
                    idx = candidate
                    break
        used.add(idx)
        indices.append(idx)
    return indices


class EmulatorTagsWidget(QWidget):
    """模拟器列单元格 widget：多个彩色标签按钮 + 双击空白启动第一个模拟器。

    同名模拟器只显示一个标签（按 name 去重，保留第一个）。
    """

    def __init__(self, emulators, on_tag_click, on_blank_double_click, row,
                 parent=None, context_cb=None):
        super().__init__(parent)
        self.row = row
        self._on_tag_click = on_tag_click
        self._on_blank_double_click = on_blank_double_click
        self._context_cb = context_cb

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        if emulators:
            pairs = _dedup_emulators(emulators)
            indices = _tag_color_indices([name for name, _ in pairs])
            for (name, path), idx in zip(pairs, indices):
                btn = EmulatorTagButton(name, context_cb=self._context_cb, color_index=idx)
                btn.clicked.connect(lambda _, p=path: self._on_tag_click(self.row, p))
                layout.addWidget(btn)
        else:
            lbl = QLabel("未配置")
            lbl.setStyleSheet("color: #999; font-size: 11px;")
            layout.addWidget(lbl)
        layout.addStretch(1)

    def mouseDoubleClickEvent(self, event):
        # 双击标签间空白 → 启动第一个模拟器
        self._on_blank_double_click(self.row)

    def contextMenuEvent(self, event):
        # 转发右键到表格的上下文菜单
        if self._context_cb:
            self._context_cb(event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)


class EmulatorTagsDelegate(QStyledItemDelegate):
    """模拟器列委托：绘制彩色药丸标签（无真实 widget，性能优）。

    用 delegate 绘制替代 setCellWidget，避免大量行时创建数千个 QWidget 导致卡顿。
    单击标签 → 启动对应模拟器；右键 → 转发表格菜单。
    鼠标悬停标签时切换到 hover 色，并显示手型光标。
    """

    TAG_H = 18          # 标签高度
    TAG_PAD_X = 10      # 标签左右内边距
    TAG_SPACING = 4     # 标签间距

    def __init__(self, get_pairs_func, on_tag_click, on_context_menu, parent=None):
        super().__init__(parent)
        self._get_pairs = get_pairs_func      # () -> _visible_pairs
        self._on_tag_click = on_tag_click      # (row, emu_path)
        self._on_context_menu = on_context_menu  # (global_pos) -> None
        self._table = None
        self._hover_row = -1        # 当前 hover 的行（-1 = 无）
        self._hover_tag_idx = -1    # 当前 hover 的标签序号（-1 = 无）

    # ---------- 标签布局计算 ----------
    def _layout_tags(self, emulators, rect):
        """计算每个标签的 (name, path, QRect, color_index) 列表。"""
        tags = []
        fm = QFontMetrics(QFont(UI_FONT, 9))
        x = rect.x() + 4
        y = rect.y() + (rect.height() - self.TAG_H) // 2
        pairs = _dedup_emulators(emulators)
        indices = _tag_color_indices([name for name, _ in pairs])
        for (name, path), idx in zip(pairs, indices):
            tw = fm.horizontalAdvance(name)
            pw = tw + self.TAG_PAD_X * 2
            tag_rect = QRect(x, y, pw, self.TAG_H)
            tags.append((name, path, tag_rect, idx))
            x += pw + self.TAG_SPACING
        return tags

    # ---------- 绘制 ----------
    def paint(self, painter, option, index):
        pairs = self._get_pairs()
        row = index.row()
        if not (0 <= row < len(pairs)):
            return
        system, _entry = pairs[row]

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # 先由 style 绘制单元格背景（选中高亮 / 交替行色），与其它列一致
        # 注意：option.widget 可能为 None（大量重绘/滚动时），必须用 qApp.style() 兜底，否则崩溃
        opt = QStyleOptionViewItem(option)
        opt.text = ""
        opt.icon = QIcon()
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)

        if not system.emulators:
            painter.setPen(QColor("#999"))
            painter.setFont(QFont(UI_FONT, 9))
            painter.drawText(option.rect, Qt.AlignVCenter | Qt.AlignLeft, "未配置")
            painter.restore()
            return

        tags = self._layout_tags(system.emulators, option.rect)
        is_hover_row = (row == self._hover_row)
        for i, (name, _path, rect, idx) in enumerate(tags):
            bg, fg, hover_bg = EmulatorTagButton.PALETTE[idx]
            # 鼠标悬停在此标签上 → 用 hover 色
            if is_hover_row and i == self._hover_tag_idx:
                bg = hover_bg
            painter.setBrush(QColor(bg))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, self.TAG_H // 2, self.TAG_H // 2)
            painter.setPen(QColor(fg))
            painter.setFont(QFont(UI_FONT, 9))
            painter.drawText(rect, Qt.AlignCenter, name)
        painter.restore()

    def sizeHint(self, option, index):
        pairs = self._get_pairs()
        row = index.row()
        if 0 <= row < len(pairs):
            system, _ = pairs[row]
            tags = self._layout_tags(system.emulators, option.rect)
            w = sum(r.width() for _, _, r, _ in tags) + self.TAG_SPACING * max(0, len(tags) - 1) + 8
            return QSize(max(w, 60), self.TAG_H + 4)
        return QSize(60, self.TAG_H + 4)

    # ---------- 点击事件 ----------
    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonPress:
            pairs = self._get_pairs()
            row = index.row()
            if not (0 <= row < len(pairs)):
                return False
            system, _ = pairs[row]
            if event.button() == Qt.LeftButton:
                tags = self._layout_tags(system.emulators, option.rect)
                for _name, path, rect, _idx in tags:
                    if rect.contains(event.pos()):
                        self._on_tag_click(row, path)
                        return True
            elif event.button() == Qt.RightButton:
                self._on_context_menu(event.globalPos())
                return True
        return False

    # ---------- hover 跟踪 ----------
    def install_hover(self, table):
        """在表格视口上启用鼠标跟踪 + 事件过滤器，实现标签 hover 效果。"""
        self._table = table
        table.viewport().setMouseTracking(True)
        table.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if self._table and obj == self._table.viewport():
            et = event.type()
            if et == QEvent.MouseMove:
                self._handle_hover(event.pos())
            elif et == QEvent.Leave:
                self._clear_hover()
        return super().eventFilter(obj, event)

    def _handle_hover(self, pos):
        """根据鼠标位置计算 hover 的标签，更新状态并重绘受影响单元格。"""
        index = self._table.indexAt(pos)
        if not index or not index.isValid() or index.column() != 2:
            self._set_hover(-1, -1)
            self._table.viewport().unsetCursor()
            return
        row = index.row()
        pairs = self._get_pairs()
        if not (0 <= row < len(pairs)):
            self._set_hover(-1, -1)
            self._table.viewport().unsetCursor()
            return
        system, _ = pairs[row]
        rect = self._table.visualRect(index)
        tags = self._layout_tags(system.emulators, rect)
        new_tag_idx = -1
        for i, (_n, _p, tag_rect, _idx) in enumerate(tags):
            if tag_rect.contains(pos):
                new_tag_idx = i
                break
        self._set_hover(row, new_tag_idx)
        if new_tag_idx >= 0:
            self._table.viewport().setCursor(Qt.PointingHandCursor)
        else:
            self._table.viewport().unsetCursor()

    def _set_hover(self, row, tag_idx):
        """更新 hover 状态；若变化则重绘旧/新行的模拟器单元格。"""
        if self._hover_row == row and self._hover_tag_idx == tag_idx:
            return
        old_row = self._hover_row
        self._hover_row = row
        self._hover_tag_idx = tag_idx
        if self._table is None:
            return
        model = self._table.model()
        if 0 <= old_row < model.rowCount():
            self._table.update(model.index(old_row, 2))
        if 0 <= row < model.rowCount():
            self._table.update(model.index(row, 2))

    def _clear_hover(self):
        """清除 hover 状态（鼠标离开表格时调用）。"""
        self._set_hover(-1, -1)
        if self._table:
            self._table.viewport().unsetCursor()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self.scale = get_scale()

        self._scan_cache = {}       # system.id -> (signature, entries)
        self._all_pairs = []        # 全部 (system, entry)
        self._visible_pairs = []    # 过滤后 (system, entry)
        self._icon_cache = {}
        self._running_games = []    # [(process, stem, emu_name)]
        self._launching = False     # 防抖：启动后短时间忽略其他启动请求

        self._favorites_only = False
        self._system_filter = set()  # 选中的平台 id 集合，空集合表示"全部平台"

        self.setWindowTitle("Oneline")
        # 窗口尺寸：直接使用配置值（默认 986×780，适配 4K/2K/1080P）
        w, h = self.config.window_width, self.config.window_height
        self.resize(w, h)
        self.setMinimumSize(int(700 * self.scale), int(460 * self.scale))

        self._build_ui()
        self._collect_all_pairs()
        self._apply_filter()

        # 监视模拟器进程，退出后自动恢复前端
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(400)
        self._watch_timer.timeout.connect(self._check_running_games)

    # ============================================================
    # UI 构建
    # ============================================================
    def _build_ui(self):
        self._build_toolbar()

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["游戏名称", "平台", "模拟器"])
        # 模拟器列改为标签展示，整表只读
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        # 文字超出单元格宽度时不换行，右侧省略号截断；行高固定单行
        self.table.setWordWrap(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        # 整表用 NoFocusDelegate（清除焦点框），模拟器列单独用标签委托绘制
        self.table.setItemDelegate(NoFocusDelegate(self))
        self._emu_delegate = EmulatorTagsDelegate(
            get_pairs_func=lambda: self._visible_pairs,
            on_tag_click=self._launch_with,
            on_context_menu=self._show_context_menu_global,
            parent=self,
        )
        self.table.setItemDelegateForColumn(2, self._emu_delegate)
        # 启用模拟器标签的鼠标 hover 效果（hover 色切换 + 手型光标）
        self._emu_delegate.install_hover(self.table)
        # 右键菜单（模拟器列的右键由 delegate.editorEvent 处理，其他列走这里）
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        font_size = max(10, int(10 * self.scale))
        self.table.setFont(QFont(UI_FONT, font_size))
        icon_size = int(26 * self.scale)
        self.table.setIconSize(QSize(icon_size, icon_size))
        self.table.verticalHeader().setDefaultSectionSize(int(34 * self.scale))

        header = self.table.horizontalHeader()
        hfont = QFont(UI_FONT, font_size)
        hfont.setBold(True)
        header.setFont(hfont)
        header.setFixedHeight(int(28 * self.scale))
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionsMovable(True)
        header.setStretchLastSection(True)
        # 列宽：保存值优先；默认 [467, 220]（游戏名称 / 平台，模拟器列自动拉伸）
        saved = self.config.column_widths
        defaults = [467, 220]
        for i in range(2):
            width = saved[i] if i < len(saved) and saved[i] > 0 else defaults[i]
            self.table.setColumnWidth(i, width)

        self.table.doubleClicked.connect(self._on_double_click)
        self.setCentralWidget(self.table)

        self.status = self.statusBar()
        self.status.showMessage(self._default_status())

    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(int(18 * self.scale), int(18 * self.scale)))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        style = QApplication.style()

        def add_icon(icon, text, tip, slot, shortcut=None):
            act = QAction(icon, text, self)
            act.setToolTip(tip)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(slot)
            toolbar.addAction(act)
            return act

        # 新增平台（导入设置，内含平台管理）—— 原"管理所有平台"按钮已移除，
        # 平台管理整合到此按钮弹出的 Tab 对话框中
        add_icon(style.standardIcon(QStyle.SP_FileDialogNewFolder), "导入设置",
                 "导入设置（新增平台 / 管理平台）", self._on_import_settings, QKeySequence.New)
        # 刷新按钮紧跟"导入设置"按钮右边
        add_icon(style.standardIcon(QStyle.SP_BrowserReload), "刷新",
                 "刷新游戏列表 (F5)", self._refresh_all, QKeySequence.Refresh)

        toolbar.addSeparator()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索游戏名称…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(int(240 * self.scale))
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit)

        # 平台筛选按钮（替代原"清除搜索"按钮）
        self._build_filter_menu()
        self.filter_btn = QToolButton()
        self.filter_btn.setIcon(style.standardIcon(QStyle.SP_FileDialogListView))
        self.filter_btn.setToolTip("平台筛选")
        self.filter_btn.clicked.connect(self._show_filter_menu)
        toolbar.addWidget(self.filter_btn)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)  # 防抖：大量数据时避免每次按键都重建表格
        self._search_timer.timeout.connect(self._apply_filter)

    # ============================================================
    # 筛选菜单
    # ============================================================
    def _build_filter_menu(self):
        """初始化空菜单与 action 容器；实际项在 _show_filter_menu 每次动态构建。"""
        self._filter_menu = QMenu(self)
        self._sys_actions = {}  # key: "__fav__"/"__all__"/平台name -> QAction

    def _show_filter_menu(self):
        """每次展开时动态刷新平台列表（多选 + 同名去重）。

        菜单顺序：我的收藏 → 全部平台 → 分割线 → 其他配置平台。
        - 我的收藏 / 全部平台：单选互斥，勾选其一则另一个及所有平台项取消
        - 其他平台：可多选，勾选任一则我的收藏 / 全部平台自动取消
        - 平台项不显示 icon，仅文字 + 勾选标记
        """
        m = self._filter_menu
        # 移除旧平台项
        for act in list(self._sys_actions.values()):
            m.removeAction(act)
        self._sys_actions.clear()

        # 1. 我的收藏（单选）
        fav_act = m.addAction("我的收藏")
        fav_act.setCheckable(True)
        fav_act.setChecked(self._favorites_only and not self._system_filter)
        fav_act.triggered.connect(self._toggle_favorites_filter)
        self._sys_actions["__fav__"] = fav_act

        # 2. 全部平台（单选）
        all_act = m.addAction("全部平台")
        all_act.setCheckable(True)
        all_act.setChecked(not self._favorites_only and not self._system_filter)
        all_act.triggered.connect(self._select_all_systems)
        self._sys_actions["__all__"] = all_act

        # 3. 分割线
        m.addSeparator()

        # 4. 其他平台（多选，同名去重，不显示 icon）
        seen_names = set()
        for s in self.config.systems:
            disp_name = s.name or "未命名平台"
            if disp_name in seen_names:
                continue
            seen_names.add(disp_name)
            act = m.addAction(disp_name)
            act.setCheckable(True)
            act.setChecked(any(sid in self._system_filter for sid in
                               [x.id for x in self.config.systems if (x.name or "未命名平台") == disp_name]))
            name = disp_name
            act.triggered.connect(lambda _, _n=name: self._toggle_system_by_name(_n))
            self._sys_actions[name] = act

        pos = self.filter_btn.mapToGlobal(QPoint(0, self.filter_btn.height()))
        m.exec_(pos)

    def _toggle_favorites_filter(self):
        """点'我的收藏'：切换收藏筛选（单选，与'全部平台'/其他平台互斥）。"""
        # 当前已处于收藏模式 → 取消，回到全部平台
        if self._favorites_only and not self._system_filter:
            self._favorites_only = False
        else:
            # 进入收藏模式：清空平台筛选
            self._favorites_only = True
            self._system_filter.clear()
        self._apply_filter()

    def _on_fav_toggled(self, checked):
        # 兼容旧信号（实际由 _toggle_favorites_filter 处理）
        self._favorites_only = checked
        if checked:
            self._system_filter.clear()
        self._apply_filter()

    def _select_all_systems(self):
        """点'全部平台'：清空所有筛选（单选，与'我的收藏'/其他平台互斥）。"""
        self._favorites_only = False
        self._system_filter.clear()
        self._apply_filter()

    def _toggle_system_by_name(self, name):
        """按平台名切换筛选：勾选则加入该 name 下所有平台 id，取消则移除。
        勾选任一平台 → 自动取消'我的收藏'和'全部平台'（进入多选模式）。
        若取消后无任何平台选中 → 回到'全部平台'。
        """
        ids = [s.id for s in self.config.systems if (s.name or "未命名平台") == name]
        if not ids:
            return
        # 任一已选中 → 视为取消整组
        if any(i in self._system_filter for i in ids):
            for i in ids:
                self._system_filter.discard(i)
        else:
            # 勾选平台：取消我的收藏
            self._favorites_only = False
            for i in ids:
                self._system_filter.add(i)
        self._apply_filter()

    # ============================================================
    # 数据：扫描 / 缓存 / 过滤
    # ============================================================
    @staticmethod
    def _signature(system):
        sig = [system.roms_dir, system.lst_file]
        for p in (system.roms_dir, system.lst_file):
            try:
                st = os.stat(p) if p else None
                sig.append((st.st_mtime_ns, st.st_size) if st else None)
            except OSError:
                sig.append(None)
        return tuple(sig)

    def _scan_system(self, system, force=False):
        sig = self._signature(system)
        cached = self._scan_cache.get(system.id)
        if not force and cached and cached[0] == sig:
            return cached[1]
        entries = scan_games(system)
        self._scan_cache[system.id] = (sig, entries)
        return entries

    def _collect_all_pairs(self, force=False):
        pairs = []
        for system in self.config.systems:
            if not system.roms_dir or not os.path.isdir(system.roms_dir):
                continue
            for entry in self._scan_system(system, force):
                pairs.append((system, entry))
        self._all_pairs = pairs

    def _on_search_changed(self):
        self._search_timer.start(120)

    def _default_status(self):
        """状态栏只显示游戏数量，不显示平台等描述信息。"""
        total = len(self._all_pairs)
        return f"共 {total} 个游戏" if total else "未找到 ROM，请检查 ROMS 目录或点击刷新"

    def _apply_filter(self):
        keyword = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        visible = []
        for system, entry in self._all_pairs:
            if keyword and keyword not in entry.display_name.lower() and keyword not in entry.filename.lower():
                continue
            if self._favorites_only and not self.config.is_favorite(system.id, entry.filename):
                continue
            if self._system_filter and system.id not in self._system_filter:
                continue
            visible.append((system, entry))
        self._visible_pairs = visible
        self._fill_table()

        # 状态栏只反映当前列表数量：有搜索/筛选时显示 命中数/总数，否则显示总数
        total = len(self._all_pairs)
        if keyword or self._favorites_only or self._system_filter:
            self.status.showMessage(f"显示 {len(visible)} / {total}" if total else "共 0 个游戏")
        else:
            self.status.showMessage(self._default_status())

    # ============================================================
    # 表格填充
    # ============================================================
    def _fill_table(self):
        table = self.table
        pairs = self._visible_pairs
        n = len(pairs)
        # 清除 hover 状态（行内容可能已变化，避免残留指向错误行）
        if hasattr(self, "_emu_delegate"):
            self._emu_delegate._clear_hover()
        table.setUpdatesEnabled(False)
        try:
            # 只在行数差异大时才 setRowCount(0) 重建；差异小则增删尾部行，减少抖动
            cur = table.rowCount()
            if cur == 0 or abs(cur - n) > 50:
                table.setRowCount(0)
                table.setRowCount(n)
            elif n < cur:
                table.setRowCount(n)
            else:
                table.setRowCount(n)

            font = QFont(UI_FONT, max(10, int(10 * self.scale)))
            fav_color = QColor("#d93025")
            type_color = QColor("#777")
            for row, (system, entry) in enumerate(pairs):
                icon = self._icon_cache.get(system.id)
                if icon is None:
                    path = icon_path(system)
                    icon = QIcon(path) if os.path.isfile(path) else QIcon()
                    self._icon_cache[system.id] = icon

                # 游戏名称（收藏游戏标红）
                name_item = QTableWidgetItem(entry.display_name)
                name_item.setToolTip(entry.filepath)
                if icon and not icon.isNull():
                    name_item.setIcon(icon)
                name_item.setFont(font)
                name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                if self.config.is_favorite(system.id, entry.filename):
                    name_item.setForeground(fav_color)
                table.setItem(row, 0, name_item)

                # 平台
                type_item = QTableWidgetItem(system.name)
                type_item.setForeground(type_color)
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 1, type_item)

                # 模拟器列：空 item（标签由 EmulatorTagsDelegate 绘制，不创建 widget）
                # 必须保留 ItemIsSelectable：整行选中时该列的 option.state 才会带
                # State_Selected，delegate 才能把背景画成选中蓝（否则只有前两列变蓝）
                emu_item = QTableWidgetItem("")
                emu_item.setFlags(emu_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 2, emu_item)
        finally:
            table.setUpdatesEnabled(True)

    def _on_double_click(self, index):
        # 双击行（非标签区域）→ 启动第一个模拟器
        if 0 <= index.row() < len(self._visible_pairs):
            self._launch_first(index.row())

    # ============================================================
    # 运行与进程监视
    # ============================================================
    def _launch_first(self, row):
        """双击行：用第一个模拟器运行。"""
        if self._launching:
            return
        if not (0 <= row < len(self._visible_pairs)):
            return
        self.table.selectRow(row)
        system, entry = self._visible_pairs[row]
        if not system.emulators:
            QMessageBox.warning(self, "无法运行", "请先在导入设置中配置模拟器路径。")
            return
        self._launch(system, entry, system.emulators[0])

    def _launch_with(self, row, emu_path):
        """单击模拟器标签：用对应模拟器运行。"""
        if self._launching:
            return
        if not (0 <= row < len(self._visible_pairs)):
            return
        self.table.selectRow(row)
        system, entry = self._visible_pairs[row]
        emu = next((e for e in system.emulators if e.path == emu_path), None)
        if not emu:
            return
        self._launch(system, entry, emu)

    def _launch(self, system, entry, emu):
        if not emu or not emu.path:
            QMessageBox.warning(self, "无法运行", "请先在导入设置中配置模拟器路径。")
            return

        # 模拟器路径：相对路径基准 = APP_DIR，统一转绝对路径（cwd 用绝对路径更稳定）
        emu_path = emu.path
        if not os.path.isabs(emu_path):
            emu_path = os.path.abspath(os.path.join(APP_DIR, emu_path))
        emu_dir = os.path.dirname(emu_path)

        # ROM 路径：绝对路径原样传；相对路径转成相对于模拟器目录
        # （前端扫描时相对路径基准 = APP_DIR，模拟器运行时 cwd = 模拟器目录，基准不同需转换）
        rom_path = entry.filepath
        if not os.path.isabs(rom_path):
            rom_abs = os.path.abspath(os.path.join(APP_DIR, rom_path))
            rom_path = os.path.relpath(rom_abs, emu_dir)

        # ROM 所在目录：同样处理
        romdir = system.roms_dir
        if romdir and not os.path.isabs(romdir):
            romdir_abs = os.path.abspath(os.path.join(APP_DIR, romdir))
            romdir = os.path.relpath(romdir_abs, emu_dir)

        stem = os.path.splitext(entry.filename)[0]
        cmd = emu.command or '"{emulator}" "{rom}"'
        for key, val in (("{emulator}", emu_path), ("{rom}", rom_path),
                         ("{romname}", entry.filename), ("{romstem}", stem),
                         ("{romdir}", romdir)):
            cmd = cmd.replace(key, val)
        try:
            proc = subprocess.Popen(cmd, shell=False, cwd=emu_dir)
        except Exception as ex:
            QMessageBox.critical(self, "启动失败", f"无法启动模拟器：\n{ex}\n\n命令：{cmd}")
            return

        # 防抖：500ms 内忽略其他启动请求，避免双击标签触发两次
        self._launching = True
        QTimer.singleShot(500, self._reset_launching)

        self._running_games.append((proc, stem, emu.name))
        self.hide()
        self._watch_timer.start()

    def _reset_launching(self):
        self._launching = False

    def _check_running_games(self):
        if not self._running_games:
            self._watch_timer.stop()
            return
        finished = [g for g in self._running_games if g[0].poll() is not None]
        if not finished:
            return
        for g in finished:
            self._running_games.remove(g)
        if not self._running_games:
            self._watch_timer.stop()
            self.show()
            self.raise_()
            self.activateWindow()

    # ============================================================
    # 右键菜单
    # ============================================================
    def _show_context_menu_global(self, global_pos):
        """标签 widget/按钮转发右键：全局坐标 → viewport 坐标，复用表格菜单。"""
        viewport_pos = self.table.viewport().mapFromGlobal(global_pos)
        self._show_context_menu(viewport_pos)

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        if not (0 <= row < len(self._visible_pairs)):
            return
        self.table.selectRow(row)
        system, entry = self._visible_pairs[row]

        menu = QMenu(self)

        # 启动游戏（多模拟器时展开子菜单选择）
        launch_act = menu.addAction("启动游戏")
        if len(system.emulators) > 1:
            sub = QMenu(menu)
            for emu in system.emulators:
                name = emu.name or os.path.basename(emu.path) or "模拟器"
                act = sub.addAction(name)
                p = emu.path
                act.triggered.connect(lambda _, _r=row, _p=p: self._launch_with(_r, _p))
            launch_act.setMenu(sub)
        else:
            launch_act.triggered.connect(lambda _, _r=row: self._launch_first(_r))

        menu.addSeparator()

        # 添加到收藏 / 从收藏中移除
        is_fav = self.config.is_favorite(system.id, entry.filename)
        if is_fav:
            fav_act = menu.addAction("从收藏中移除")
        else:
            fav_act = menu.addAction("添加到收藏")
        fav_act.triggered.connect(lambda _, _r=row: self._toggle_favorite_row(_r))

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _toggle_favorite_row(self, row):
        if not (0 <= row < len(self._visible_pairs)):
            return
        system, entry = self._visible_pairs[row]
        self.config.toggle_favorite(system.id, entry.filename)
        self.config.save()
        # 刷新当前行的收藏标记
        name_item = self.table.item(row, 0)
        if name_item:
            if self.config.is_favorite(system.id, entry.filename):
                name_item.setForeground(QColor("#d93025"))
            else:
                name_item.setForeground(QColor())  # 默认颜色
        # 处于收藏筛选模式时，移除后需重新过滤
        if self._favorites_only and not self.config.is_favorite(system.id, entry.filename):
            self._apply_filter()

    # ============================================================
    # 操作
    # ============================================================
    def _refresh_all(self):
        self._collect_all_pairs(force=True)
        self._apply_filter()

    def _on_import_settings(self):
        """打开导入设置 Tab 对话框（新增平台 / 管理平台）。"""
        dlg = ImportSettingsDialog(self.config.systems, self)
        dlg.exec_()
        if dlg.result_changed():
            # 清掉所有平台的缓存后全量重建（编辑/删除/新增都可能影响 ROM 与图标）
            self._scan_cache.clear()
            self._icon_cache.clear()
            self.config.save()
            self._collect_all_pairs(force=True)
            self._apply_filter()

    def closeEvent(self, event):
        self.config.window_width = self.width()
        self.config.window_height = self.height()
        self.config.column_widths = [self.table.columnWidth(i) for i in range(2)]
        self.config.save()
        event.accept()
