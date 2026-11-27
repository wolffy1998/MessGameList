# -*- coding: utf-8 -*-
"""导入设置：Tab 对话框，包含「新增平台」表单与「平台管理」列表。

平台管理的「新增/编辑」直接切到「新增平台」Tab 载入数据，不再弹出独立对话框。
新增平台 Tab 兼任编辑：编辑模式下按钮变为「保存修改」，保存后切回管理列表。
"""
import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QGroupBox, QMessageBox, QScrollArea, QWidget,
    QTabWidget, QFrame, QCheckBox,
)
from config import SystemConfig, Emulator, icon_path, DEFAULT_COMMAND


PLACEHOLDER_HELP = (
    "<div style='line-height:180%;'>"
    "<b>运行指令模板占位符：</b><br>"
    "{emulator} = 模拟器路径<br>"
    "{rom} = ROM 完整路径（含后缀）<br>"
    "{romname} = ROM 文件名（含后缀）<br>"
    "{romstem} = ROM 文件名（不含后缀）<br>"
    "{romdir} = ROM 所在目录<br>"
    "示例：&quot;{emulator}&quot; -fullscreen &quot;{rom}&quot;"
    "</div>"
)


class EmulatorRow:
    """一行模拟器配置：名称 / 路径 / 运行指令。"""
    def __init__(self, name="", path="", command=DEFAULT_COMMAND):
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("名称，如 RetroArch")
        self.path_edit = QLineEdit(path)
        self.path_edit.setPlaceholderText("可执行文件路径 (.exe)")
        self.command_edit = QLineEdit(command)
        self.command_edit.setPlaceholderText(DEFAULT_COMMAND)

        self.path_btn = QPushButton("浏览…")
        self.path_btn.setFixedWidth(56)
        self.path_btn.clicked.connect(self._pick_path)

    def _pick_path(self):
        p, _ = QFileDialog.getOpenFileName(None, "选择模拟器程序", self.path_edit.text() or "",
                                           "可执行文件 (*.exe *.bat *.cmd);;所有文件 (*)")
        if p:
            self.path_edit.setText(p)
            if not self.name_edit.text():
                self.name_edit.setText(os.path.splitext(os.path.basename(p))[0])

    def to_emulator(self):
        return Emulator(
            name=self.name_edit.text().strip(),
            path=self.path_edit.text().strip(),
            command=self.command_edit.text().strip() or DEFAULT_COMMAND,
        )

    def widgets(self):
        return self.name_edit, self.path_edit, self.path_btn, self.command_edit


# ============================================================
# 平台设置表单（新增/编辑，嵌入 Tab）
# ============================================================
class SettingsPage(QWidget):
    """平台设置表单：新增 / 编辑，嵌入 Tab。

    新增模式：按钮「添加平台」，apply 后发出 system_added（副本）并重置表单。
    编辑模式：按钮「保存修改」，apply 后发出 system_saved（已原地修改的对象）。
    """

    system_added = pyqtSignal(SystemConfig)   # 新增成功
    system_saved = pyqtSignal(SystemConfig)   # 编辑保存

    def __init__(self, system: SystemConfig = None, parent=None):
        super().__init__(parent)
        self.system = system if system else SystemConfig()
        self.emulator_rows = []
        self._editing_system = None     # None=新增模式，否则=正在编辑的对象
        self._build_ui()
        self.start_new()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(10)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ---- 平台信息 ----
        basic = QGroupBox("平台信息")
        fb = QFormLayout(basic)
        fb.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：任天堂 FC / SFC / PS1")
        fb.addRow("平台名称：", self.name_edit)

        form.addWidget(basic)

        # ---- ROM 与列表 ----
        paths = QGroupBox("ROM 与列表")
        fp = QFormLayout(paths)
        fp.setSpacing(8)

        self.roms_edit = QLineEdit()
        self.roms_edit.setPlaceholderText("存放 ROM 文件的目录")
        roms_btn = QPushButton("浏览…")
        roms_btn.clicked.connect(self._pick_roms)
        rl = QHBoxLayout(); rl.setSpacing(6); rl.addWidget(self.roms_edit); rl.addWidget(roms_btn)
        fp.addRow("ROMS 目录：", rl)

        self.lst_edit = QLineEdit()
        self.lst_edit.setPlaceholderText("可选，TAB 分割的 .lst / .glt 文件（只取前两列）")
        lst_btn = QPushButton("浏览…")
        lst_btn.clicked.connect(self._pick_lst)
        ll = QHBoxLayout(); ll.setSpacing(6); ll.addWidget(self.lst_edit); ll.addWidget(lst_btn)
        fp.addRow("映射列表：", ll)

        # 仅显示列表中匹配的 ROM
        self.lst_filter_chk = QCheckBox("仅显示列表中匹配的 ROM（设置列表后，未在列表中出现的 ROM 将被隐藏）")
        self.lst_filter_chk.setToolTip("勾选后，只有能在列表文件（.lst/.glt）中匹配到的 ROM 才会出现在游戏列表中")
        fp.addRow("", self.lst_filter_chk)
        form.addWidget(paths)

        # ---- 模拟器配置 ----
        emu_box = QGroupBox("模拟器（可添加多个）")
        ev = QVBoxLayout(emu_box)
        ev.setSpacing(6)

        self.emu_container = QVBoxLayout()
        self.emu_container.setSpacing(6)
        ev.addLayout(self.emu_container)

        add_emu_btn = QPushButton("+ 添加模拟器")
        add_emu_btn.clicked.connect(lambda: self._add_emulator_row())
        ev.addWidget(add_emu_btn, alignment=Qt.AlignLeft)

        help_lbl = QLabel(PLACEHOLDER_HELP)
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet(
            "color: #888; font-size: 11px; background: #f7f7f7; "
            "padding: 6px; border-radius: 3px;"
        )
        ev.addWidget(help_lbl)
        form.addWidget(emu_box)
        # 关键：末尾加 stretch，吸收 QScrollArea 视口多余高度，
        # 否则三个 GroupBox 会被 QVBoxLayout 均匀拉伸（平台信息 GroupBox 只有名称一行却占很高）
        form.addStretch(1)

        # ---- 底部操作栏（在滚动区外，始终可见）----
        footer = QHBoxLayout()
        footer.setContentsMargins(10, 0, 10, 10)
        footer.setSpacing(8)
        self.mode_label = QLabel("新增模式")
        self.mode_label.setStyleSheet("color: #1a73e8; font-weight: bold;")
        footer.addWidget(self.mode_label)
        footer.addStretch(1)
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self._on_reset)
        footer.addWidget(self.reset_btn)
        self.add_btn = QPushButton("添加平台")
        self.add_btn.clicked.connect(self._on_action)
        self.add_btn.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; padding: 6px 18px; border-radius: 3px; }"
            "QPushButton:hover { background: #1765cc; }"
        )
        footer.addWidget(self.add_btn)
        root.addLayout(footer)

    # ---------- 模式切换 ----------
    def start_new(self):
        """切到新增模式：空白表单。"""
        self._editing_system = None
        self.system = SystemConfig()
        self._load_from_system()
        self.add_btn.setText("添加平台")
        self.mode_label.setText("新增模式")

    def start_edit(self, system):
        """切到编辑模式：载入指定平台数据。"""
        self._editing_system = system
        self.system = system
        self._load_from_system()
        self.add_btn.setText("保存修改")
        self.mode_label.setText(f"编辑：{system.name}")

    def _on_reset(self):
        if self._editing_system is not None:
            # 编辑模式：重新载入原始数据
            self._load_from_system()
        else:
            # 新增模式：清空
            self.start_new()

    # ---------- 目录 ----------
    def _pick_roms(self):
        p = QFileDialog.getExistingDirectory(self, "选择 ROMS 目录", self.roms_edit.text() or "")
        if p:
            self.roms_edit.setText(p)

    def _pick_lst(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择映射列表文件", self.lst_edit.text() or "",
                                           "映射列表 (*.lst *.glt *.txt);;所有文件 (*)")
        if p:
            self.lst_edit.setText(p)

    # ---------- 模拟器行 ----------
    def _add_emulator_row(self, name="", path="", command=DEFAULT_COMMAND):
        row = EmulatorRow(name, path, command)
        self.emulator_rows.append(row)

        item = QFrame()
        item.setStyleSheet("QFrame { border: 1px solid #e5e5e5; border-radius: 3px; background: #fcfcfc; }")
        hl = QHBoxLayout(item)
        hl.setContentsMargins(8, 6, 8, 6)
        hl.setSpacing(6)
        for w in row.widgets():
            hl.addWidget(w)
        rm = QPushButton("删除")
        rm.setFixedWidth(48)
        rm.setToolTip("移除此模拟器")
        rm.setStyleSheet("QPushButton { color: #c5221f; }")
        hl.addWidget(rm)
        rm.clicked.connect(lambda: self._remove_emulator_row(row, item))

        self.emu_container.addWidget(item)

    def _remove_emulator_row(self, row, widget):
        if row in self.emulator_rows:
            self.emulator_rows.remove(row)
        self.emu_container.removeWidget(widget)
        widget.deleteLater()

    # ---------- 载入 / 应用 ----------
    def _load_from_system(self):
        s = self.system
        self.name_edit.setText(s.name)
        self.roms_edit.setText(s.roms_dir)
        self.lst_edit.setText(s.lst_file)
        self.lst_filter_chk.setChecked(bool(getattr(s, "lst_filter_only", False)))
        # 清空旧行
        while self.emulator_rows:
            row = self.emulator_rows.pop()
            self._remove_emulator_row(row, row.widgets()[0].parentWidget())
        for e in s.emulators:
            self._add_emulator_row(e.name, e.path, e.command)
        if not s.emulators:
            self._add_emulator_row()

    def _apply(self):
        """验证并写入 self.system，成功返回 True。"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写平台名称。")
            return False
        roms = self.roms_edit.text().strip()
        if roms and not os.path.isdir(roms):
            QMessageBox.warning(self, "提示", "ROMS 目录不存在，请检查。")
            return False
        lst = self.lst_edit.text().strip()
        if lst and not os.path.isfile(lst):
            QMessageBox.warning(self, "提示", "LST 文件不存在，请检查。")
            return False

        self.system.name = name
        self.system.roms_dir = roms
        self.system.lst_file = lst
        self.system.lst_filter_only = self.lst_filter_chk.isChecked()
        emus = [r.to_emulator() for r in self.emulator_rows]
        self.system.emulators = [e for e in emus if e.name or e.path]
        return True

    def _on_action(self):
        if not self._apply():
            return
        if self._editing_system is not None:
            # 编辑模式：system 已被 _apply 原地修改，通知外部刷新
            self.system_saved.emit(self.system)
        else:
            # 新增模式：发出副本并重置表单
            added = SystemConfig(
                name=self.system.name,
                icon=self.system.icon,
                roms_dir=self.system.roms_dir,
                lst_file=self.system.lst_file,
                lst_filter_only=self.system.lst_filter_only,
                emulators=list(self.system.emulators),
            )
            self.system_added.emit(added)
            self.start_new()

    # 兼容旧调用
    def reset_for_new(self):
        self.start_new()


# ============================================================
# 平台管理页面（可嵌入）
# ============================================================
class SystemManagerPage(QWidget):
    """平台管理列表：新增/编辑/删除。

    新增、编辑均通过 edit_requested 信号请求外部切到「新增平台」Tab 载入数据，
    不再弹出独立对话框。
    """

    changed = pyqtSignal()
    edit_requested = pyqtSignal(object)   # None=新增, SystemConfig=编辑

    def __init__(self, systems, parent=None):
        super().__init__(parent)
        self.systems = systems          # 直接引用 config.systems（活列表）
        self._build_ui()
        self._reload()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._edit)
        root.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        for text, slot in (("新增", self._add), ("编辑", self._edit), ("删除", self._delete)):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        root.addLayout(row)

    def reload(self, keep_id=None):
        """供外部调用刷新列表。"""
        self._reload(keep_id=keep_id)

    def _reload(self, keep_id=None):
        self.list.clear()
        for s in self.systems:
            item = QListWidgetItem(s.name or "未命名平台")
            p = icon_path(s)
            if os.path.isfile(p):
                item.setIcon(QIcon(p))
            item.setData(Qt.UserRole, s.id)
            item.setToolTip(f"模拟器 {len(s.emulators)} 个\nROMS：{s.roms_dir or '未设置'}")
            self.list.addItem(item)
        if keep_id:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole) == keep_id:
                    self.list.setCurrentRow(i)
                    break
        elif self.list.count() and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)

    def _current_system(self):
        item = self.list.currentItem()
        if not item:
            return None
        sid = item.data(Qt.UserRole)
        return next((s for s in self.systems if s.id == sid), None)

    def _add(self):
        # 切到新增 Tab（空白表单），不弹对话框
        self.edit_requested.emit(None)

    def _edit(self):
        s = self._current_system()
        if not s:
            QMessageBox.information(self, "提示", "请先在列表中选择一个平台。")
            return
        # 切到新增 Tab 载入该平台数据，不弹对话框
        self.edit_requested.emit(s)

    def _delete(self):
        s = self._current_system()
        if not s:
            QMessageBox.information(self, "提示", "请先在列表中选择一个平台。")
            return
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定删除平台「{s.name}」的配置吗？\n（不会删除 ROM 文件）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.systems[:] = [x for x in self.systems if x.id != s.id]
            self.changed.emit()
            self._reload()


# ============================================================
# 导入设置 Tab 对话框（主入口）
# ============================================================
class ImportSettingsDialog(QDialog):
    """导入设置：Tab 对话框，整合「新增平台」+「平台管理」。

    平台管理的「新增/编辑」直接切到「新增平台」Tab 载入数据，不再弹出独立对话框。
    点击工具栏「导入设置」按钮后弹出此对话框。
    """

    def __init__(self, systems, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导入设置")
        self.setModal(True)
        # 去掉标题栏右上角的 "?"（What's This）帮助按钮，只保留关闭按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(860, 640)
        self.systems = systems          # 直接引用 config.systems（活列表）
        self._changed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self.tabs = QTabWidget()

        # Tab1：新增平台（兼编辑）
        self.add_page = SettingsPage(parent=self)
        self.add_page.system_added.connect(self._on_system_added)
        self.add_page.system_saved.connect(self._on_system_saved)
        self._tab_add_idx = self.tabs.addTab(self.add_page, "新增平台")

        # Tab2：平台管理
        self.manager_page = SystemManagerPage(systems, parent=self)
        self.manager_page.changed.connect(self._on_manager_changed)
        self.manager_page.edit_requested.connect(self._on_edit_requested)
        self._tab_mgr_idx = self.tabs.addTab(self.manager_page, "平台管理")

        root.addWidget(self.tabs, 1)

    def _on_edit_requested(self, system):
        """平台管理请求新增/编辑：切到「新增平台」Tab 载入数据。"""
        if system is None:
            self.add_page.start_new()
            self.tabs.setTabText(self._tab_add_idx, "新增平台")
        else:
            self.add_page.start_edit(system)
            self.tabs.setTabText(self._tab_add_idx, "编辑平台")
        self.tabs.setCurrentIndex(self._tab_add_idx)

    def _on_system_added(self, system):
        """新增成功：加入列表、刷新管理页、切回管理列表。"""
        self.systems.append(system)
        self._changed = True
        self.manager_page.reload(keep_id=system.id)
        self.tabs.setTabText(self._tab_add_idx, "新增平台")
        self.tabs.setCurrentIndex(self._tab_mgr_idx)

    def _on_system_saved(self, system):
        """编辑保存：刷新管理页、复位新增 Tab、切回管理列表。"""
        self._changed = True
        self.manager_page.reload(keep_id=system.id)
        self.add_page.start_new()
        self.tabs.setTabText(self._tab_add_idx, "新增平台")
        self.tabs.setCurrentIndex(self._tab_mgr_idx)

    def _on_manager_changed(self):
        self._changed = True

    def result_changed(self):
        return self._changed
