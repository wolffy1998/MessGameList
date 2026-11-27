# -*- coding: utf-8 -*-
"""Oneline - 程序入口。"""
import sys
import os

from ui_scale import enable_high_dpi

enable_high_dpi()  # 必须在 QApplication 创建之前调用

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QFont

from config import APP_ICON, DEFAULT_ICON
from ui_scale import get_scale
from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Oneline")
    app.setFont(QFont("Microsoft YaHei UI", max(9, int(9 * get_scale(app)))))

    # 窗口图标优先用多尺寸 ICO，回退到默认 PNG
    icon_file = APP_ICON if os.path.isfile(APP_ICON) else DEFAULT_ICON
    if os.path.isfile(icon_file):
        app.setWindowIcon(QIcon(icon_file))

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
