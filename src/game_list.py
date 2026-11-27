# -*- coding: utf-8 -*-
"""游戏列表逻辑：扫描 ROM 文件，读取 lst/glt 映射表，生成游戏条目。

映射文件（.lst / .glt，解析规则完全相同）格式：
  每行 2 列或 3 列，以制表符(\\t)分割，**只取前两列**。
    第一列 = ROM 文件名（不含路径、不含扩展名）
    第二列 = 显示的游戏名称
    第三列（如有）= 忽略，不影响映射
  - 以 // 开头的行（可含前导空白）视为注释，直接忽略
  - 空行直接忽略
  - 常见 glt 头部如 `// codepage=1252` 会被解析为编码提示辅助解码
匹配规则：游戏名（ROM 文件名，不含后缀，小写）匹配第一列（同样去后缀/路径、小写），
  匹配成功则显示第二列的值，否则显示游戏文件名（不含后缀）。
编码自动识别（UTF-8 / GBK / Big5 / Shift-JIS 等）。
"""
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# 读取文本文件时尝试的编码顺序（charset_normalizer 无法判断时的兜底）
FALLBACK_ENCODINGS = ["utf-8-sig", "utf-8", "gb18030", "big5", "shift_jis", "cp1252", "latin-1"]

# Windows codepage 号 → Python 编码名（用于 // codepage=N 注释提示）
CODEPAGE_MAP = {
    1252: "cp1252",    # 西欧
    936: "gb18030",    # 简体中文 GBK/GB18030
    932: "shift_jis",  # 日文
    949: "cp949",      # 韩文
    950: "big5",       # 繁体中文
    65001: "utf-8",    # UTF-8
    437: "cp437",      # DOS 西欧
}


@dataclass
class GameEntry:
    filename: str          # 实际文件名（含后缀）
    filepath: str          # 完整路径
    display_name: str      # 显示名称（lst 映射后或文件名）
    system_name: str = ""  # 平台名称


def _score_text(text: str) -> float:
    """给解码结果打分：中文字符越多分越高，出现乱码特征字则扣分。"""
    if not text:
        return -1e9
    score = 0.0
    cjk = 0
    # 常见乱码区域（韩文音节 / 西里尔 / 希腊 等）——中文 lst 里不应出现
    garbage = 0
    for ch in text:
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            cjk += 1
        elif 0xAC00 <= code <= 0xD7AF or 0x0400 <= code <= 0x04FF or 0x0370 <= code <= 0x03FF:
            garbage += 1
    score += cjk * 2.0 - garbage * 3.0
    return score


def _detect_codepage(raw: bytes):
    """从文件头注释中探测 // codepage=N 提示，返回 Python 编码名或 None。

    glt 模板头部常见：
      // game list translation template for FinalBurn Neo version 0x100003
      // codepage=1252
    用 ASCII/latin-1 读头部注释即可（注释本身是 ASCII）。
    """
    head = raw[:4096].decode("latin-1", errors="replace")
    m = re.search(r"^\s*//\s*codepage\s*=\s*(\d+)\s*$", head, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    try:
        cp = int(m.group(1))
    except ValueError:
        return None
    return CODEPAGE_MAP.get(cp)


def read_text_auto(path: str) -> str:
    """自动识别编码读取文本文件（针对中文 ROM 列表优化）。

    优先级：UTF-8 BOM → 严格 UTF-8 → 文件头 // codepage=N 提示 → 候选编码打分 → charset_normalizer。
    """
    raw = open(path, "rb").read()
    if not raw:
        return ""

    # 1) UTF-8 BOM 明确标识
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass

    # 2) 严格 UTF-8（无 BOM）优先——UTF-8 解码成功通常就是正确的
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # 3) 文件头 // codepage=N 注释提示（如 FinalBurn Neo 的 glt 模板）
    hinted = _detect_codepage(raw)
    if hinted:
        try:
            return raw.decode(hinted)
        except (UnicodeDecodeError, LookupError):
            pass

    # 4) 候选编码逐个解码并打分，选最优
    hint_set = {hinted} if hinted else set()
    best_text, best_score = None, -1e9
    for enc in FALLBACK_ENCODINGS:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        s = _score_text(text)
        # 提示编码同等分数下优先
        if hinted and enc in hint_set:
            s += 0.5
        if s > best_score:
            best_text, best_score = text, s
    if best_text is not None:
        return best_text

    # 5) 最后交给 charset_normalizer（仅作为兜底）
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(raw).best()
        if best and best.encoding:
            return str(best)
    except Exception:
        pass

    return raw.decode("utf-8", errors="replace")


def parse_lst(path: str) -> Dict[str, str]:
    """解析 lst/glt 映射文件，返回 {ROM名(小写,无后缀): 显示名称}。

    每行以制表符分割，可能为 2 列或 3 列，只取前两列：
      第一列 = ROM 名（去路径/后缀、转小写）作为匹配键
      第二列 = 显示名称（第三列及以后忽略）
    以 // 开头的行（可含前导空白）及空行直接忽略。
    """
    mapping = {}
    if not path or not os.path.isfile(path):
        return mapping

    text = read_text_auto(path)
    for line in text.splitlines():
        line = line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped:
            continue
        # 忽略 // 注释行（如 glt 模板头部的版本说明、codepage 提示）
        if stripped.startswith("//"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        key = parts[0].strip()
        value = parts[1].strip()   # 只取第二列，第三列及以后一律忽略
        if not key or not value:
            continue
        # 去掉 key 可能的扩展名和路径
        key = os.path.splitext(os.path.basename(key))[0].lower()
        mapping[key] = value
    return mapping


def scan_games(system, lst_path_override: Optional[str] = None) -> List[GameEntry]:
    """扫描平台的 roms 目录，返回游戏条目列表。

    system: SystemConfig 实例
    lst_path_override: 可选，覆盖平台自带的 lst 路径
    """
    roms_dir = system.roms_dir
    entries: List[GameEntry] = []

    if not roms_dir or not os.path.isdir(roms_dir):
        return entries

    lst_path = lst_path_override if lst_path_override is not None else system.lst_file
    mapping = parse_lst(lst_path) if lst_path else {}
    # 设置了 .lst 且启用"仅显示匹配项"时，只保留 mapping 中列出的 ROM
    lst_filter_only = bool(getattr(system, "lst_filter_only", False)) and bool(mapping)

    try:
        names = os.listdir(roms_dir)
    except OSError:
        return entries

    for name in sorted(names, key=lambda s: s.lower()):
        full = os.path.join(roms_dir, name)
        if not os.path.isfile(full):
            continue
        # 跳过隐藏文件
        if name.startswith("."):
            continue

        stem, _ext = os.path.splitext(name)
        stem_key = stem.lower()
        # 启用 lst 过滤时，跳过不在列表中的 ROM
        if lst_filter_only and stem_key not in mapping:
            continue
        display = mapping.get(stem_key, stem)
        entries.append(GameEntry(
            filename=name,
            filepath=full,
            display_name=display,
            system_name=system.name,
        ))

    return entries
