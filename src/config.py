# -*- coding: utf-8 -*-
"""配置数据模型与持久化。

配置结构（config.json）：
{
  "systems": [
    {
      "id": "uuid",
      "name": "平台名称",
      "icon": "图标路径或空",
      "roms_dir": "roms目录",
      "lst_file": "lst路径或空",
      "emulators": [
        {"name": "模拟器名", "path": "exe路径", "command": "\"{emulator}\" \"{rom}\""}
      ]
    }
  ],
  "last_system_id": "上次选中的平台",
  "window": {"width": 986, "height": 780}
}
"""
import os
import sys
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# 源码运行时：项目目录；打包后：exe 所在目录（配置写在这里，不进只读的 _internal）
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
# 内置资源目录：源码运行时同项目目录；打包后为 PyInstaller 解包目录
RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
# 允许用环境变量覆盖配置路径（测试隔离用），正常运行不受影响
CONFIG_PATH = os.environ.get("EMUFRONT_CONFIG", "") or os.path.join(APP_DIR, "config.json")
DEFAULT_ICON = os.path.join(RESOURCE_DIR, "resources", "default_icon.png")
# 程序图标（窗口 + exe 文件图标）：多尺寸 ICO，视觉与默认平台图标一致
APP_ICON = os.path.join(RESOURCE_DIR, "resources", "app.ico")

# 默认运行指令模板：引号包裹路径，兼容带空格的路径
DEFAULT_COMMAND = '"{emulator}" "{rom}"'


@dataclass
class Emulator:
    name: str = ""
    path: str = ""
    command: str = DEFAULT_COMMAND

    def to_dict(self):
        return {"name": self.name, "path": self.path, "command": self.command}

    @staticmethod
    def from_dict(d: dict):
        return Emulator(
            name=d.get("name", ""),
            path=d.get("path", ""),
            command=d.get("command", DEFAULT_COMMAND) or DEFAULT_COMMAND,
        )


@dataclass
class SystemConfig:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "新平台"
    icon: str = ""                 # 自定义图标路径；空则用默认（兼容旧配置，UI 不再设置）
    roms_dir: str = ""
    lst_file: str = ""
    lst_filter_only: bool = False  # 设置了 .lst 文件时，仅显示列表中匹配的 ROM
    emulators: List[Emulator] = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "roms_dir": self.roms_dir,
            "lst_file": self.lst_file,
            "lst_filter_only": self.lst_filter_only,
            "emulators": [e.to_dict() for e in self.emulators],
        }

    @staticmethod
    def from_dict(d: dict):
        return SystemConfig(
            id=d.get("id") or uuid.uuid4().hex,
            name=d.get("name", "新平台"),
            icon=d.get("icon", ""),
            roms_dir=d.get("roms_dir", ""),
            lst_file=d.get("lst_file", ""),
            lst_filter_only=d.get("lst_filter_only", False),
            emulators=[Emulator.from_dict(e) for e in d.get("emulators", [])],
        )


@dataclass
class AppConfig:
    systems: List[SystemConfig] = field(default_factory=list)
    last_system_id: str = ""
    window_width: int = 986
    window_height: int = 780
    column_widths: List[int] = field(default_factory=lambda: [467, 220])  # 游戏列表各列宽度（默认 4K/2K/1080P 通用）
    favorites: List[str] = field(default_factory=list)      # 喜爱的游戏：["system_id|filename", ...]

    def to_dict(self):
        return {
            "systems": [s.to_dict() for s in self.systems],
            "last_system_id": self.last_system_id,
            "window": {"width": self.window_width, "height": self.window_height},
            "column_widths": self.column_widths,
            "favorites": self.favorites,
        }

    @staticmethod
    def from_dict(d: dict):
        w = d.get("window", {})
        return AppConfig(
            systems=[SystemConfig.from_dict(s) for s in d.get("systems", [])],
            last_system_id=d.get("last_system_id", ""),
            window_width=w.get("width", 986),
            window_height=w.get("height", 780),
            column_widths=d.get("column_widths", [467, 220]),
            favorites=d.get("favorites", []),
        )

    def save(self, path=CONFIG_PATH):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path=CONFIG_PATH):
        if not os.path.exists(path):
            return AppConfig()
        try:
            # 先尝试 utf-8（本程序写出的配置）
            with open(path, "r", encoding="utf-8") as f:
                return AppConfig.from_dict(json.load(f))
        except Exception:
            # 兼容其他编码的配置
            from charset_normalizer import from_path
            try:
                best = from_path(path).best()
                if best:
                    return AppConfig.from_dict(json.loads(str(best)))
            except Exception:
                pass
            return AppConfig()

    def get_system(self, sid):
        for s in self.systems:
            if s.id == sid:
                return s
        return None

    # ---------- 喜爱游戏 ----------
    @staticmethod
    def fav_key(system_id: str, filename: str) -> str:
        """生成喜爱游戏的唯一标识。"""
        return f"{system_id}|{filename}"

    def is_favorite(self, system_id: str, filename: str) -> bool:
        return self.fav_key(system_id, filename) in self.favorites

    def toggle_favorite(self, system_id: str, filename: str) -> bool:
        """切换喜爱状态，返回切换后是否为喜爱。"""
        key = self.fav_key(system_id, filename)
        if key in self.favorites:
            self.favorites.remove(key)
            return False
        self.favorites.append(key)
        return True


def icon_path(system: SystemConfig) -> str:
    """返回平台图标路径：自定义优先，否则默认。"""
    if system.icon and os.path.isfile(system.icon):
        return system.icon
    return DEFAULT_ICON
