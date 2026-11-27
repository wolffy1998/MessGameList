# -*- coding: utf-8 -*-
"""高分屏适配辅助：1080p / 2K / 4K 自动调节 UI 尺寸。"""
from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication

_SCALE = 1.0


def enable_high_dpi():
    """必须在 QApplication 创建之前调用。"""
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def get_scale(app=None):
    """返回 UI 缩放系数。

    Windows 已在 4K 下开启 150%/200% 缩放时，Qt 会自动处理，此处只补
    一层"舒适系数"：物理分辨率高但系统缩放仍为 100% 时放大 UI。
    """
    global _SCALE
    if app is None:
        app = QApplication.instance()
    if app is None:
        return _SCALE
    screen = app.primaryScreen()
    if screen is None:
        return _SCALE
    dpr = screen.devicePixelRatio()
    phys_w = screen.geometry().width() * dpr
    if dpr <= 1.25:
        if phys_w >= 3500:
            _SCALE = 1.30
        elif phys_w >= 2500:
            _SCALE = 1.15
        else:
            _SCALE = 1.0
    else:
        _SCALE = 1.0
    return _SCALE
