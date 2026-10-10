# MessGameList

> MAME MESS 软件列表（hash 目录中的 XML）汉化工具
> Rust + [egui](https://github.com/emilk/egui) 桌面 GUI

一个轻量的本地化工具：读取 MAME `hash` 目录下的软件列表 XML，以表格展示每条记录的
`name` / `description`，让你在右侧输入中文描述，再把译文写回 XML 或汇总到
`mess.lst` 公共列表中。

---

## 功能特性

### 浏览与编辑

- **列表选择**：顶部下拉框列出 `hash` 目录下的全部 `.xml` 软件列表
- **三列表格**：`Name`（等宽字体）、`Description`（原文）、`Rename`（汉化输入框）
- **虚拟滚动**：仅渲染可见行，几千条记录也保持流畅
- **状态指示**：已汉化条目显示绿色圆点，未汉化显示橙色圆点
- **文本可选中复制**：`Name` / `Description` 两列整格可框选，双向拖拽，`Ctrl+C` 复制
- **进度统计**：工具栏实时显示 `已汉化 / 总数` 与百分比
- **排序辅助**
  - 📌 **置顶**：把未汉化的条目全部移到前面，方便继续翻译
  - ↩ **还原**：恢复为 XML 中的原始顺序

### 写入 XML

把 `Rename` 列中已填写的内容写回**当前** XML 文件：

- 仅替换 `<description>` 的文本内容，**保留文件其余字节与格式**（含 BOM、缩进、注释）
- 写入前弹出确认框，显示目标文件、写入条目数与当前完成度
- 未填写任何内容时主按钮自动禁用

### mess.lst 公共列表

`mess.lst` 是制表符分隔的两列文本，用于跨 XML 共享译文：

```
a2600.xml_adventp	冒险岛
a2600.xml_pacman	吃豆人
```

- **第一列**固定为 `文件名_name`（如 `a2600.xml_adventp`），保证跨文件唯一
- **📥 导入**：预读 `mess.lst`，统计出「可导入 N 条」，只填充 `Rename` 为空的条目，**不覆盖**已有汉化
- **📤 导出**：把当前 XML 已填写的译文追加到 `mess.lst`，同前缀（`<文件名>__`）的旧条目会被本次导出替换；导出会显示「将导出 N 条 / 列表现有 M 条」

### 界面细节

- 浅色专业配色，表格斑马纹 + 悬停高亮 + 网格线
- 所有弹窗为模态对话框：半透明遮罩、居中、点击遮罩或按 `Esc` 关闭
- 工具栏在窄窗口 / 高 DPI 下自动横向滚动，按钮不会被裁剪
- 内嵌中文字体（微软雅黑 / 黑体 / 宋体），跨平台一致显示

---

## 快速开始

### 环境要求

- Rust 1.85+ （edition 2024）
- Windows / macOS / Linux

### 运行

```bash
cargo run --release
```

### 准备数据

程序在**当前工作目录**下寻找数据，因此请把可执行文件（或 `cargo run` 的工作目录）放在包含以下内容的位置：

```
<工作目录>/
├── hash/                 ← MAME 的 hash 目录（内含 *.xml 软件列表）
│   ├── a2600.xml
│   ├── mame.xml
│   └── ...
└── mess.lst              ← 可选，公共汉化列表（不存在时自动创建）
```

> 直接 `cargo run` 时工作目录即项目根目录，项目内已附带 `hash/sample_*.xml`
> 两个样例文件可用于快速验证界面。

### 操作流程

1. 顶部下拉框选择要汉化的 XML 列表
2. 在 `Rename` 列逐行输入中文描述
3. 用「置顶 / 还原」整理翻译顺序
4. **📤 导出 mess.lst**：把当前译文并入公共列表（建议先做，便于跨文件复用与备份）
5. **💾 写入 XML**：把译文写回源文件（有确认弹窗）
6. 换一个 XML 时用 **📥 导入 mess.lst** 自动带入已有译文

---

## 项目结构

```
MessGameList/
├── Cargo.toml            # 依赖：eframe / roxmltree / rfd / encoding_rs
├── src/
│   ├── lib.rs            # crate 入口
│   ├── hanhua.rs         # 核心逻辑：XML 解析/写回、mess.lst 读写、CJK 检测（含单元测试）
│   └── main.rs           # egui GUI：表格、工具栏、弹窗
└── hash/                 # 数据目录（XML 软件列表）
```

### 核心模块 `hanhua.rs`

| 函数 | 说明 |
| --- | --- |
| `list_xml_files` | 列出目录下的 `.xml` 文件 |
| `parse_xml_file` | 解析 XML，返回 `Entry { name, description, translation }` |
| `write_translations` | 仅替换 `<description>` 文本，其余字节原样保留 |
| `read_mess_list` / `write_mess_list` | 读写制表符分隔的两列列表 |
| `make_key` | 生成 `文件名_name` 唯一键 |
| `sanitize_field` | 清理列表字段中的制表符 / 换行 |
| `has_cjk` | 判断是否含中文字符 |

---

## 开发

```bash
cargo build --release      # 构建
cargo test                 # 运行 hanhua.rs 单元测试
cargo clippy               # 静态检查
```

---

## 注意事项

- 写入 XML 会**直接修改源文件且不可撤销**，建议先用「导出 mess.lst」备份
- 请保持 `mess.lst` 使用 **UTF-8 / 制表符分隔 / 两列** 格式
- `mess.lst` 第一列的 `文件名` 部分需与 `hash` 目录下的 XML 文件名（含扩展名）一致

---

## 许可证

见 [LICENSE](LICENSE)。