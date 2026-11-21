# MessGameList

为 MAME MESS 软件列表 XML（hash 目录）批量填写中文译名，并写回 XML 或汇总到 `mess.lst` 的桌面工具。



## 一、概述

工具读取 MAME `hash` 目录下的软件列表 XML，以表格展示每条记录的 `name` / `description`，在 `Rename` 列填写中文，再把译文写回 XML，或汇总到 `mess.lst` 公共列表供其他 XML 复用。



## 二、界面与操作

### 工具栏

从左到右依次为：

| 控件 | 说明 |
| --- | --- |
| `XML 列表` 下拉框 | 列出 `hash/` 下的全部 `.xml`；切换即加载。展开时按字母键可滚动定位到首个首字母匹配项（只滚动，不改变选中项） |
| 进度徽标 | `已汉化/总数 (百分比%)`，列表为空时不显示 |
| `📌 置顶` | 把未汉化条目按原始顺序稳定前置，已汉化条目保持原相对顺序 |
| `↩ 还原` | 恢复 XML 中的原始顺序 |
| `📥 导入 mess.lst` | 打开导入确认框（见下） |
| `📤 导出 mess.lst` | 打开导出确认框（见下） |
| `💾 写入 XML` | 主操作（强调蓝）；打开写入确认框 |
| `关于` | 版本号与联系方式 |

- 未选择 XML 或列表为空时，工具栏按钮除「关于」外全部禁用（下拉框仍可用来选择文件）。
- 窗口过窄 / 高 DPI 缩放下工具栏自动横向滚动，按钮不会被裁剪。
- `hash/` 只在程序启动时扫描一次，运行期间新增 XML 需重启程序。

### 表格

- 三列：`Name`（等宽字体）、`Description`（原文）、`Rename`（汉化输入框，占位提示「输入中文描述…」）。
- 列宽自适应窗口：`Name` 限制在 150–190px，`Rename` 限制在 300–400px，`Description` 占剩余空间（最小 240px）。
- 行高 38px；表头固定，数据区虚拟滚动（只渲染可见行），几千条记录也不卡顿。
- 斑马纹 + 行悬停高亮 + 网格线；表头与数据行列宽一致。
- 状态圆点：已汉化绿色，未汉化橙色（警告色）。
- 已汉化行的输入框变为浅绿底 + 绿框 + 绿字，与未汉化的白底灰框区分。
- `Name` / `Description` 整格可选中复制：命中区覆盖整列（含空白处），支持双向拖拽框选，`Ctrl+C` 复制。

### 写入 XML

把 `Rename` 列中非空的内容写回**当前** XML 文件：

- 只替换已有 `<description>` 元素的文本，文件其余字节（BOM、缩进、注释、DTD、属性写法）原样保留。
- 写入内容做 XML 转义（`& < > " '`）。
- **同步 `alt_title`**：若译文以括号结尾（`(日本)` 或全角 `（日本）`），会去掉结尾括号并写入同一 `software` 下
  `<info name="alt_title" value="…"/>` 的 `value`；没有该 `info` 节点时不做任何改动。
- 没有 `<description>` 子节点的 `software` 会被跳过，不计入写入条数。
- XML 必须为 UTF-8（允许 BOM），否则直接报错、不修改文件。
- 确认框显示：目标文件、写入条目数、写入字段（`description`）、完成度进度条，并提示「直接修改源文件且不可撤销」。
  写入条目为 0 时「确认写入」按钮禁用。
- 写入完成/失败后弹出结果弹窗，底部状态栏同步显示结果。

### mess.lst 导入 / 导出

`mess.lst` 是制表符分隔的两列文本，第一列为唯一键、第二列为译文：

```
a2600__adventp	冒险岛
a2600__pacman	吃豆人
```

- 键格式为 `XML文件名去掉.xml扩展名__name`（双下划线），例如 `a2600.xml` 中 `name="adventp"` → `a2600__adventp`。
- **导入**：
  - 确认框显示：来源文件（不存在时标红）、当前列表、可导入 N 条、空白条目 M 条。
  - 按当前 XML 的键填充 `Rename` 为空的条目，已有汉化绝不覆盖。
  - `mess.lst` 不存在或可导入为 0 时，「开始导入」禁用。
- **导出**：
  - 确认框显示：目标文件、当前列表、将导出 N 条、列表现有 M 条，并提示同前缀 `文件名__` 的旧条目会被本次导出替换。
  - 写出过程：读取旧表 → 删除第一列以 `文件名__` 开头的条目 → 追加当前 XML 的已填译文（制表符/换行折叠为空格）
    → **按第一列自然序排序整张表** → 整体重写。
  - 自然序：数字片段按数值比较（`s2` 在 `s10` 前），其余忽略大小写；数值相同但写法不同（`s02` / `s2`）再按原串比较，保证全序。
  - 当前已填译文为 0 时「确认导出」禁用；`mess.lst` 不存在时导出会自动创建。



## 三、源码目录

```
MessGameList/
├── Cargo.toml       # 依赖声明与包信息
├── Cargo.lock       # 依赖版本锁定（已提交，保证各机版本一致）
├── src/
│   ├── main.rs      # GUI 界面与交互：工具栏、虚拟滚动表格、确认框
│   ├── lib.rs       # 库入口，仅导出 hanhua 模块
│   └── hanhua.rs    # 核心逻辑：XML 解析与写回、mess.lst 读写
├── LICENSE
└── README.md
```

`hanhua.rs` 提供核心函数（解析 XML、写回 `description` 与 `alt_title`、读写 `mess.lst`）；`main.rs` 负责界面与操作，通过 `mess_gamelist::hanhua` 调用核心逻辑。



## 四、项目构建

### 环境要求

- 构建：Rust 1.85+（edition 2024），Windows / macOS / Linux 均可编译
- 运行：发布产物为 Windows 可执行文件，最低 Windows 10

### 常用命令

| 命令                    | 说明                                                         |
| ----------------------- | ------------------------------------------------------------ |
| `cargo build --release` | 构建发布版 → `target/release/MessGameList.exe`               |
| `cargo build`           | 构建调试版 → `target/debug/MessGameList.exe`                 |
| `cargo run --release`   | 构建并运行                                                   |
| `cargo build --release --offline` | 依赖已缓存时离线构建                                 |
| `cargo test`            | 运行全部测试：`hanhua.rs` 8 个单元测试 + `main.rs` 3 个悬停回归测试 |
| `cargo clippy`          | 静态检查                                                     |
| `cargo tree --depth 1`  | 只看直接依赖                                                 |
| `cargo tree -i eframe`  | 查某个包为什么被引入                                         |
| `cargo update`          | 升级依赖版本                                                 |
| `cargo vendor`          | 把依赖复制进项目 `vendor/`（离线 / 内网构建）                |
| `cargo clean`           | 清理 `target/`                                               |

> `Cargo.lock` 已提交，依赖版本一致；依赖存放在全局 `~/.cargo/registry` 跨项目共享，缓存命中后不再联网。

> GNU 工具链下运行 `cargo test` 链接测试程序时，除了 `gcc`，还需要 MinGW 的 `binutils`/导入库在 PATH 上，
> 否则会报 `cannot find -lshlwapi` 或 `dlltool.exe: program not found`；把 MinGW 的 `bin` 目录整体加入 PATH 即可。



### Windows 工具链：两条路线二选一

Rust 自身不含 C 代码，但**生成 `.exe` 必须调用系统链接器**。两条路线**二选一即可，不需要同时配置**。
先确认当前工具链：

```powershell
rustc -vV | Select-String host
```

| `host` 输出              | 链接器               | 需要安装                    |
| ------------------------ | -------------------- | --------------------------- |
| `x86_64-pc-windows-gnu`  | `gcc.exe` → `ld.exe` | MinGW-w64 / MSYS2           |
| `x86_64-pc-windows-msvc` | `link.exe`           | Visual Studio / Build Tools |

> ⚠️ **用哪条路线由 Rust 工具链本身决定，与 PATH 上有什么无关。**
> PATH 里有 `cl.exe` 不会让 GNU 工具链改用 MSVC；PATH 里有 `gcc.exe` 也不会让 MSVC 工具链改用 GCC。

#### 路线 A：GNU（MinGW / MSYS2）

```powershell
# 安装（scoop 会自动配好 PATH）
scoop install rust-gnu mingw
# 或使用已安装的 MSYS2：C:\msys64\ucrt64\bin

gcc --version        # 验证
cargo build --release
```

`gcc` 在 PATH 上就能编译，不需要任何配置文件。

**指定链接器路径的几种方式：**

若 `cargo build` 报 ``linker `cc` not found``，以下四种方式任选，**按优先级从高到低**：

1️⃣ `RUSTFLAGS` 环境变量（优先级最高，对当前终端生效）

```powershell
$env:RUSTFLAGS = "-C linker=C:\mingw64\bin\gcc.exe"
cargo build --release
```

2️⃣ `CARGO_TARGET_<TRIPLE>_LINKER` 环境变量

```powershell
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER = "C:\mingw64\bin\gcc.exe"
cargo build --release
```

3️⃣ Cargo 配置文件（推荐，可固化到项目里）

**项目级**——新建 `.cargo\config.toml`，只影响本项目：

```toml
[target.x86_64-pc-windows-gnu]
linker = "C:\\mingw64\\bin\\gcc.exe"
# 可选：附加链接参数
rustflags = ["-C", "link-arg=-static-libgcc"]
```

**用户级**——新建 `~/.cargo/config.toml`，对本机所有项目生效：

```toml
[target.x86_64-pc-windows-gnu]
linker = "C:\\mingw64\\bin\\gcc.exe"
```

> ⚠️ 配置文件里路径要用**双反斜杠** `\\`，或改用正斜杠 `/`（`C:/mingw64/bin/gcc.exe`）也能识别。
> `.cargo/config.toml` 已在 `.gitignore` 中，不会提交到仓库，避免写死他人机器的路径。
> 注意：只配 `linker` 只解决 `cc not found`，不解决 `-lshlwapi` / `dlltool`，后者仍需 MinGW `bin` 在 PATH 上。

4️⃣ 临时把目录加进当前终端的 PATH（最省事）

```powershell
$env:PATH += ";C:\mingw64\bin"
cargo build --release
```

只对当前窗口有效；想永久生效可在「系统属性 → 环境变量」中添加。

> **优先级**：`RUSTFLAGS` > `CARGO_TARGET_<TRIPLE>_LINKER` > `.cargo/config.toml`（项目级优先于用户级）> PATH 自动查找

MSVC 路线通常直接在 **Developer PowerShell for VS** 中编译即可；也可手动指定：

```powershell
$env:RUSTFLAGS = "-C linker=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\<版本号>\bin\Hostx64\x64\link.exe"
```



#### 路线 B：MSVC（Visual Studio / Build Tools）

```powershell
winget install Rustlang.Rustup                          # rustup 默认装 MSVC 工具链
winget install Microsoft.VisualStudio.2022.BuildTools   # 勾选「使用 C++ 的桌面开发」
cargo build --release
```

此路线**完全不需要 GCC / MinGW / MSYS2**。



## 五、运行时目录

程序只从**当前工作目录**找数据，目录结构必须为：

```
<运行目录>/
├── MessGameList.exe
├── hash/                 ← MAME 的 hash 目录，内含 *.xml 软件列表
│   ├── a2600.xml
│   └── ...
└── mess.lst              ← 可选；导入时不存在按 0 条处理，导出时自动创建
```

- 把 exe 放到 MAME 的 `hash/` 同级目录（或把 `hash/` 复制到 exe 旁边）即可。
- 仓库**不附带** `hash/` 与 `mess.lst`；直接 `cargo run` 时工作目录是项目根，若根目录没有 `hash/`，
  界面会显示空状态提示。
- `hash/` 在启动时扫描一次，运行中新放入的 XML 需要重启后才会出现在下拉框。



## 六、数据格式

### XML 写回规则

| 项目 | 行为 |
| --- | --- |
| 编码 | 必须 UTF-8（可带 BOM）；BOM 在写回时保留 |
| 解析 | 允许 `<!DOCTYPE …>`（MAME hash 文件常见）；收集所有带 `name` 属性的 `<software>` |
| 修改范围 | 仅 `<description>` 元素整体替换；`alt_title` 仅在其 `value` 需要变化时替换属性值内部 |
| 其他字节 | 缩进、换行、注释、属性引号风格、其余元素全部原样保留 |
| 跳过条件 | 无 `<description>` 子节点，或该条目译文为空 |



### mess.lst 格式

| 项目 | 行为 |
| --- | --- |
| 列结构 | 两列，制表符分隔；第一列为键，第二列为译文 |
| 键格式 | `文件名去扩展名__name`（双下划线） |
| 读取编码 | 先 UTF-8（自动去 BOM），失败回退 GBK |
| 写出编码 | UTF-8（无 BOM），行尾 CRLF |
| 读取容错 | 跳过空行与不含制表符的行；两列首尾空白会 trim |
| 写出顺序 | 整张表按第一列自然序排序 |
| 字段清理 | 译文中的制表符 / 回车 / 换行折叠为单个空格，避免破坏列结构 |



## 七、许可证

见 [LICENSE](LICENSE)。
