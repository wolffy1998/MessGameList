#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;

use eframe::egui;
// egui_extras 不再使用 TableBuilder（其列分配在该环境异常），改为手写虚拟滚动表格
use mess_hanhua_tool::hanhua::{self, Entry};

// ============================================================
// 专业浅色配色体系（参考 VS Code / JetBrains 浅色主题）
// ============================================================
// 文字
const C_TEXT: egui::Color32       = egui::Color32::from_rgb(40, 40, 40);
const C_TEXT_SEC: egui::Color32   = egui::Color32::from_rgb(80, 80, 80);
const C_TEXT_MUTED: egui::Color32 = egui::Color32::from_rgb(140, 140, 140);
// 强调色
const C_ACCENT: egui::Color32     = egui::Color32::from_rgb(0, 112, 192);
const C_ACCENT_LIGHT: egui::Color32 = egui::Color32::from_rgb(230, 242, 255);
// 状态色
const C_SUCCESS: egui::Color32    = egui::Color32::from_rgb(0, 150, 60);
const C_SUCCESS_LIGHT: egui::Color32 = egui::Color32::from_rgb(232, 245, 233);
const C_WARNING: egui::Color32    = egui::Color32::from_rgb(255, 152, 0);
const C_WARNING_LIGHT: egui::Color32 = egui::Color32::from_rgb(255, 248, 225);
const C_DANGER: egui::Color32     = egui::Color32::from_rgb(213, 0, 0);
const C_DANGER_LIGHT: egui::Color32 = egui::Color32::from_rgb(255, 235, 238);
// 背景层级（表格条纹背景色直接复用 C_BG_ROW_B）
const C_BG: egui::Color32         = egui::Color32::from_rgb(250, 250, 252);
const C_BG_PANEL: egui::Color32   = egui::Color32::from_rgb(255, 255, 255);
const C_BG_ROW_B: egui::Color32   = egui::Color32::from_rgb(247, 247, 249);
// 边框
const C_BORDER: egui::Color32     = egui::Color32::from_rgb(218, 220, 224);
const C_BORDER_STRONG: egui::Color32 = egui::Color32::from_rgb(180, 185, 190);
// 状态栏
const C_STATUS_OK_BG: egui::Color32 = egui::Color32::from_rgb(240, 248, 240);
const C_STATUS_ERR_BG: egui::Color32 = egui::Color32::from_rgb(255, 245, 245);

struct App {
    hash_dir: String,
    mess_lst_path: String,
    xml_files: Vec<String>,
    selected_file: Option<String>,
    entries: Vec<(usize, Entry)>,
    default_order: Vec<usize>,
    display_order: Vec<usize>,
    status_msg: String,
    status_ok: bool,
    confirm_write: bool,
    confirm_import: bool,
    confirm_export: bool,
    import_preview: usize,
    export_preview: usize,
    lst_total: usize,
    show_result_dialog: Option<(String, bool)>,
    show_about_dialog: bool,
}

impl App {
    fn new() -> Self {
        let cwd = std::env::current_dir()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        let hash_dir = std::path::Path::new(&cwd).join("hash").to_string_lossy().to_string();
        let mess_lst = std::path::Path::new(&cwd).join("mess.lst").to_string_lossy().to_string();

        let mut app = Self {
            hash_dir,
            mess_lst_path: mess_lst,
            xml_files: Vec::new(),
            selected_file: None,
            entries: Vec::new(),
            default_order: Vec::new(),
            display_order: Vec::new(),
            status_msg: "等待选择...".to_string(),
            status_ok: true,
            confirm_write: false,
            confirm_import: false,
            confirm_export: false,
            import_preview: 0,
            export_preview: 0,
            lst_total: 0,
            show_result_dialog: None,
            show_about_dialog: false,
        };
        app.scan_xml_dir();
        app
    }

    fn set_status(&mut self, msg: impl Into<String>, ok: bool) {
        self.status_msg = msg.into();
        self.status_ok = ok;
    }

    fn scan_xml_dir(&mut self) {
        match hanhua::list_xml_files(&self.hash_dir) {
            Ok(files) => {
                self.xml_files = files;
                self.selected_file = None;
                self.entries.clear();
                self.default_order.clear();
                self.display_order.clear();
                if self.xml_files.is_empty() {
                    self.set_status("当前目录下未找到 hash/ 文件夹或其中无 XML 文件", false);
                } else {
                    self.set_status(format!("就绪：共 {} 个 XML 列表", self.xml_files.len()), true);
                }
            }
            Err(e) => {
                self.set_status(format!("扫描失败：{e}"), false);
            }
        }
    }

    fn load_selected(&mut self) {
        let Some(file) = self.selected_file.clone() else { return };
        let path = hanhua::join_path(&self.hash_dir, &file);
        match hanhua::parse_xml_file(&path) {
            Ok(entries) => {
                let n = entries.len();
                self.entries = entries.into_iter().enumerate().collect();
                self.default_order = (0..n).collect();
                self.display_order = self.default_order.clone();
                self.set_status(format!("已载入 {file}，共 {n} 条记录"), true);
            }
            Err(e) => {
                self.set_status(format!("载入 {file} 失败：{e}"), false);
            }
        }
    }

    fn translated_count(&self) -> usize {
        self.entries.iter().filter(|(_, e)| !e.translation.trim().is_empty()).count()
    }

    fn untranslated_count(&self) -> usize {
        self.entries.len().saturating_sub(self.translated_count())
    }

    fn pin_up(&mut self) {
        let mut empty: Vec<usize> = Vec::new();
        let mut filled: Vec<usize> = Vec::new();
        for &i in &self.default_order {
            if self.entries[i].1.translation.trim().is_empty() {
                empty.push(i);
            } else {
                filled.push(i);
            }
        }
        empty.extend(filled);
        self.display_order = empty;
        let unt = self.untranslated_count();
        self.set_status(format!("已置顶 {unt} 条未汉化条目"), true);
    }

    fn restore_order(&mut self) {
        self.display_order = self.default_order.clone();
        self.set_status("已还原默认排序", true);
    }

    /// 打开「导入」确认框前：预读 mess.lst，统计可填充的空白条目
    fn preview_import(&mut self) {
        self.import_preview = 0;
        let Some(file) = self.selected_file.clone() else { return };
        let Ok(list) = hanhua::read_mess_list(&self.mess_lst_path) else {
            return;
        };
        let map: HashMap<&String, &String> = list.iter().map(|(k, v)| (k, v)).collect();
        self.import_preview = self
            .entries
            .iter()
            .filter(|(_, e)| e.translation.trim().is_empty())
            .filter(|(_, e)| map.contains_key(&hanhua::make_key(&file, &e.name)))
            .count();
    }

    /// 打开「导出」确认框前：统计将写出的条目数与列表当前总条目数
    fn preview_export(&mut self) {
        self.export_preview = self.translated_count();
        self.lst_total = hanhua::read_mess_list(&self.mess_lst_path)
            .map(|l| l.len())
            .unwrap_or(0);
    }

    fn write_back(&mut self) {
        let Some(file) = self.selected_file.clone() else {
            self.set_status("请先选择 XML 列表", false);
            self.show_result_dialog = Some(("请先选择 XML 列表".to_string(), false));
            return;
        };
        let mut map = HashMap::new();
        for (_, e) in &self.entries {
            let text = e.translation.trim();
            if !text.is_empty() {
                map.insert(e.name.clone(), text.to_string());
            }
        }
        if map.is_empty() {
            self.set_status("没有已输入的汉化内容", false);
            self.show_result_dialog = Some(("没有已输入的汉化内容".to_string(), false));
            return;
        }
        let path = hanhua::join_path(&self.hash_dir, &file);
        match hanhua::write_translations(&path, &map) {
            Ok(n) => {
                self.set_status(format!("已写入 {n} 条汉化到 {file}"), true);
                self.show_result_dialog =
                    Some((format!("写入成功：已写入 {n} 条汉化到 {file}"), true));
            }
            Err(e) => {
                self.set_status(format!("写入失败：{e}"), false);
                self.show_result_dialog = Some((format!("写入失败：{e}"), false));
            }
        }
    }

    fn import_mess_lst(&mut self) {
        let Some(file) = self.selected_file.clone() else {
            self.set_status("请先选择 XML 列表", false);
            self.show_result_dialog = Some(("请先选择 XML 列表".to_string(), false));
            return;
        };
        let list = match hanhua::read_mess_list(&self.mess_lst_path) {
            Ok(l) => l,
            Err(e) => {
                self.set_status(format!("读取 mess.lst 失败：{e}"), false);
                self.show_result_dialog = Some((format!("读取 mess.lst 失败：{e}"), false));
                return;
            }
        };
        let mut map = HashMap::new();
        for (k, v) in list {
            map.insert(k, v);
        }
        let mut imported = 0;
        for (_, e) in &mut self.entries {
            if !e.translation.trim().is_empty() {
                continue;
            }
            let key = hanhua::make_key(&file, &e.name);
            if let Some(v) = map.get(&key) {
                e.translation = v.clone();
                imported += 1;
            }
        }
        self.set_status(format!("已从 mess.lst 导入 {imported} 条汉化"), true);
        self.show_result_dialog = Some((format!("已从 mess.lst 导入 {imported} 条汉化"), true));
    }

    fn export_mess_lst(&mut self) {
        let Some(file) = self.selected_file.clone() else {
            self.set_status("请先选择 XML 列表", false);
            self.show_result_dialog = Some(("请先选择 XML 列表".to_string(), false));
            return;
        };
        let prefix = {
            let stem = file.strip_suffix(".xml").unwrap_or(&file);
            format!("{stem}__")
        };
        // 读取已有列表（如果存在）
        let mut all_items = match hanhua::read_mess_list(&self.mess_lst_path) {
            Ok(items) => items,
            Err(_) => Vec::new(),
        };
        // 删除当前 XML 前缀的旧条目
        all_items.retain(|(k, _)| !k.starts_with(&prefix));
        // 追加当前已输入的汉化条目
        for (_, e) in &self.entries {
            let text = e.translation.trim();
            if !text.is_empty() {
                all_items.push((
                    hanhua::make_key(&file, &e.name),
                    hanhua::sanitize_field(text),
                ));
            }
        }
        match hanhua::write_mess_list(&self.mess_lst_path, &all_items) {
            Ok(()) => {
                let exported = all_items.iter().filter(|(k, _)| k.starts_with(&prefix)).count();
                self.set_status(format!("已导出 {exported} 条到 mess.lst"), true);
                self.show_result_dialog =
                    Some((format!("已导出 {exported} 条到 mess.lst"), true));
            }
            Err(e) => {
                self.set_status(format!("导出失败：{e}"), false);
                self.show_result_dialog = Some((format!("导出失败：{e}"), false));
            }
        }
    }

    fn install_fonts(ctx: &egui::Context) {
        let mut fonts = egui::FontDefinitions::default();
        let candidates: &[(&str, u32)] = &[
            (r"C:\Windows\Fonts\msyh.ttc", 0),
            (r"C:\Windows\Fonts\msyhbd.ttc", 0),
            (r"C:\Windows\Fonts\simhei.ttf", 0),
            (r"C:\Windows\Fonts\simsun.ttc", 0),
        ];
        for (path, index) in candidates {
            if let Ok(bytes) = std::fs::read(path) {
                let is_font = bytes.len() > 4
                    && (bytes[0..4] == [0x00, 0x01, 0x00, 0x00]
                        || &bytes[0..4] == b"OTTO"
                        || &bytes[0..4] == b"ttcf");
                if is_font {
                    fonts.font_data.insert(
                        "cjk".to_owned(),
                        std::sync::Arc::new(egui::FontData {
                            font: bytes.into(),
                            index: *index,
                            tweak: Default::default(),
                        }),
                    );
                    break;
                }
            }
        }
        if fonts.font_data.contains_key("cjk") {
            for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
                let v = fonts.families.entry(family).or_default();
                v.insert(0, "cjk".to_owned());
            }
        }
        ctx.set_fonts(fonts);
    }
}

// ============================================================
// 专业按钮样式
// ============================================================
fn btn_style(ui: &mut egui::Ui, text: impl Into<String>, is_danger: bool) -> egui::Response {
    let fill = if is_danger { C_DANGER } else { C_ACCENT };
    let stroke = if is_danger { C_DANGER } else { C_ACCENT };
    let text_color = egui::Color32::WHITE;
    ui.add(
        egui::Button::new(egui::RichText::new(text).color(text_color))
            .fill(fill)
            .stroke(egui::Stroke::new(1.0, stroke)),
    )
}

// ============================================================
// 把控件放进指定矩形，并强制“水平居左 + 垂直居中 + 命中区撑满整格”
//
// 三个坑（egui 0.36）：
// 1) 不能用 Ui::put()：它内部用 Layout::centered_and_justified，
//    allocate_exact_size 会按布局把控件在矩形里水平居中。
// 2) Layout::left_to_right(Align::Center) 的参数只控制【垂直】对齐，
//    水平(main_axis)对齐被硬编码为 Align::Center，必须用
//    .with_main_align(Align::LEFT) 覆盖，否则文字仍然是居中的。
// 3) 必须再加 .with_main_justify(true)：Label 的 Response.rect 等于
//    文字宽度，不 justify 的话框选命中区只有文字那么宽，
//    空白处无法起拖、也无法反向（右→左）框选。
// ============================================================
fn put_left(ui: &mut egui::Ui, rect: egui::Rect, widget: impl egui::Widget) -> egui::Response {
    put_aligned(ui, rect, widget, egui::Align::LEFT)
}

// 同上，但可指定水平对齐方式
fn put_aligned(
    ui: &mut egui::Ui,
    rect: egui::Rect,
    widget: impl egui::Widget,
    halign: egui::Align,
) -> egui::Response {
    egui::Ui::scope_builder(
        ui,
        egui::UiBuilder::new().max_rect(rect).layout(
            egui::Layout::left_to_right(egui::Align::Center)
                .with_main_align(halign)
                .with_main_justify(true),
        ),
        |ui| ui.add(widget),
    )
    .response
}

// ============================================================
// 弹窗通用组件
// ============================================================
#[derive(Clone, Copy, PartialEq)]
enum BtnKind {
    Primary,
    Secondary,
    Danger,
}

/// 弹窗外壳：白底 + 圆角 + 柔和阴影 + 细边框
fn dialog_frame() -> egui::Frame {
    egui::Frame::default()
        .fill(C_BG_PANEL)
        .corner_radius(10.0)
        .shadow(egui::epaint::Shadow {
            offset: [0, 6],
            blur: 18,
            spread: 0,
            color: egui::Color32::from_black_alpha(48),
        })
        .inner_margin(egui::Margin::symmetric(24, 20))
        .stroke(egui::Stroke::new(1.0, C_BORDER))
}

/// 弹窗标题区：圆形图标 + 主标题 + 副标题
fn dialog_header(
    ui: &mut egui::Ui,
    icon: &str,
    icon_bg: egui::Color32,
    icon_fg: egui::Color32,
    title: &str,
    subtitle: &str,
) {
    let h = if subtitle.is_empty() { 42.0 } else { 46.0 };
    let w = ui.available_width();
    let (rect, _) = ui.allocate_exact_size(egui::vec2(w, h), egui::Sense::hover());
    let c = rect.center();
    ui.painter().circle_filled(c, 20.0, icon_bg);
    ui.painter().text(
        c,
        egui::Align2::CENTER_CENTER,
        icon,
        egui::FontId::proportional(19.0),
        icon_fg,
    );
    let x = rect.left() + 52.0;
    let title_font = egui::FontId::proportional(16.0);
    if subtitle.is_empty() {
        ui.painter().text(
            egui::pos2(x, c.y),
            egui::Align2::LEFT_CENTER,
            title,
            title_font,
            C_TEXT,
        );
    } else {
        ui.painter().text(
            egui::pos2(x, rect.top() + 8.0),
            egui::Align2::LEFT_TOP,
            title,
            title_font,
            C_TEXT,
        );
        ui.painter().text(
            egui::pos2(x, rect.top() + 29.0),
            egui::Align2::LEFT_TOP,
            subtitle,
            egui::FontId::proportional(12.0),
            C_TEXT_SEC,
        );
    }
}

/// 弹窗内的圆角信息卡片
fn dialog_card(fill: egui::Color32, stroke: Option<egui::Color32>) -> egui::Frame {
    egui::Frame::default()
        .fill(fill)
        .corner_radius(6.0)
        .inner_margin(egui::Margin::symmetric(14, 12))
        .stroke(match stroke {
            Some(c) => egui::Stroke::new(1.0, c),
            None => egui::Stroke::NONE,
        })
}

/// 卡片内的一行「标签 — 值」，值右对齐并在过长时省略
fn kv_row(ui: &mut egui::Ui, key: &str, value: &str, color: egui::Color32) {
    ui.horizontal_top(|ui| {
        ui.add(
            egui::Label::new(egui::RichText::new(key).size(12.5).color(C_TEXT_SEC)).truncate(),
        );
        let avail = ui.available_width();
        let r = egui::Rect::from_min_size(ui.cursor().left_top(), egui::vec2(avail, 20.0));
        put_aligned(
            ui,
            r,
            egui::Label::new(egui::RichText::new(value).size(12.5).color(color)).truncate(),
            egui::Align::RIGHT,
        );
    });
    ui.add_space(3.0);
}

/// 提示条（图标 + 一行说明）
fn notice_bar(ui: &mut egui::Ui, icon: &str, text: &str, bg: egui::Color32, fg: egui::Color32) {
    egui::Frame::default()
        .fill(bg)
        .corner_radius(6.0)
        .inner_margin(egui::Margin::symmetric(12, 10))
        .show(ui, |ui| {
            ui.horizontal_top(|ui| {
                ui.add(egui::Label::new(egui::RichText::new(icon).size(13.0).color(fg)));
                ui.add(
                    egui::Label::new(egui::RichText::new(text).size(12.5).color(fg)).truncate(),
                );
            });
        });
}

/// 完成度进度条：标题行 + 轨道
fn progress_bar(ui: &mut egui::Ui, done: usize, total: usize, color: egui::Color32) {
    let ratio = if total == 0 { 0.0 } else { done as f32 / total as f32 };
    ui.horizontal(|ui| {
        ui.add(egui::Label::new(
            egui::RichText::new(format!("已汉化 {done} / {total} 条"))
                .size(12.0)
                .color(C_TEXT_SEC),
        ));
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            ui.add(egui::Label::new(
                egui::RichText::new(format!("{:.0}%", ratio * 100.0))
                    .size(12.0)
                    .color(color)
                    .strong(),
            ));
        });
    });
    ui.add_space(5.0);
    let w = ui.available_width();
    let (rect, _) = ui.allocate_exact_size(egui::vec2(w, 6.0), egui::Sense::hover());
    ui.painter()
        .rect_filled(rect, 3.0, egui::Color32::from_rgb(232, 233, 236));
    if ratio > 0.0 {
        let filled = egui::Rect::from_min_max(
            rect.min,
            egui::pos2(rect.min.x + (rect.width() * ratio).max(6.0), rect.max.y),
        );
        ui.painter().rect_filled(filled, 3.0, color);
    }
}

/// 底部按钮：主按钮在最右，返回被点击的按钮
#[derive(Clone, Copy, PartialEq)]
enum DialogAction {
    Primary,
    Secondary,
    None,
}

fn dialog_buttons(
    ui: &mut egui::Ui,
    primary: Option<(&str, BtnKind)>,
    primary_enabled: bool,
    secondary: &str,
) -> DialogAction {
    let mut action = DialogAction::None;
    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
        if let Some((label, kind)) = primary {
            if ui.add_enabled(primary_enabled, dialog_btn(label, kind)).clicked() {
                action = DialogAction::Primary;
            }
            ui.add_space(8.0);
        }
        // secondary 传空串时不绘制，避免出现一个没有文字的空白按钮
        if !secondary.is_empty() && ui.add(dialog_btn(secondary, BtnKind::Secondary)).clicked() {
            action = DialogAction::Secondary;
        }
    });
    action
}

fn dialog_btn(text: &str, kind: BtnKind) -> egui::Button<'_> {
    let (fill, stroke, fg) = match kind {
        BtnKind::Primary => (C_ACCENT, C_ACCENT, egui::Color32::WHITE),
        BtnKind::Secondary => (
            egui::Color32::from_rgb(246, 246, 248),
            C_BORDER_STRONG,
            C_TEXT,
        ),
        BtnKind::Danger => (C_DANGER, C_DANGER, egui::Color32::WHITE),
    };
    egui::Button::new(egui::RichText::new(text).size(13.0).color(fg).strong())
        .fill(fill)
        .stroke(egui::Stroke::new(1.0, stroke))
        .corner_radius(5.0)
        .min_size(egui::vec2(92.0, 32.0))
}

impl eframe::App for App {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        // ---- 浅色全局视觉 ----
        let mut visuals = egui::Visuals::light();
        visuals.panel_fill = C_BG;
        visuals.window_fill = C_BG_PANEL;
        visuals.widgets.noninteractive.bg_fill = C_BG_PANEL;
        visuals.widgets.inactive.bg_fill = C_BG_PANEL;
        visuals.override_text_color = Some(C_TEXT);
        visuals.faint_bg_color = C_BG_ROW_B;
        visuals.extreme_bg_color = C_BG;
        visuals.hyperlink_color = C_ACCENT;
        ui.ctx().set_visuals(visuals);

        // ============================================================
        // 顶部工具栏 — 所有元素垂直居中对齐
        // ============================================================
        egui::Panel::top("toolbar")
            .frame(
                egui::Frame::default()
                    .fill(C_BG_PANEL)
                    .inner_margin(egui::Margin::symmetric(14, 10))
                    .stroke(egui::Stroke::new(1.0, C_BORDER)),
            )
            .show(ui, |ui| {
                // 横向滚动兜底：小窗口 / 高 DPI 缩放下按钮也不会被裁剪
                egui::ScrollArea::horizontal()
                    .id_salt("toolbar_scroll")
                    .auto_shrink(false)
                    .show(ui, |ui| {
                // 关键：使用 bottom_up 布局让所有子元素垂直居中
                ui.with_layout(egui::Layout::left_to_right(egui::Align::Center), |ui| {
                    // XML 列表标签
                    ui.label(
                        egui::RichText::new("XML 列表")
                            .size(11.5)
                            .color(C_TEXT_SEC),
                    );
                    ui.add_space(4.0);

                    // ComboBox（展开状态下支持字母键在列表内滚动定位）
                    let prev = self.selected_file.clone();
                    egui::ComboBox::from_id_salt("xml_combo")
                        .width(122.0)
                        .selected_text(
                            self.selected_file
                                .clone()
                                .unwrap_or_else(|| "请选择...".to_string()),
                        )
                        .show_ui(ui, |ui| {
                            // 仅下拉列表展开时检测字母键：滚动定位到首字母匹配项，不改变选中项
                            let ctx = ui.ctx();
                            let mut scroll_target: Option<String> = None;
                            for ch in 'a'..='z' {
                                let key = match ch {
                                    'a' => egui::Key::A, 'b' => egui::Key::B, 'c' => egui::Key::C,
                                    'd' => egui::Key::D, 'e' => egui::Key::E, 'f' => egui::Key::F,
                                    'g' => egui::Key::G, 'h' => egui::Key::H, 'i' => egui::Key::I,
                                    'j' => egui::Key::J, 'k' => egui::Key::K, 'l' => egui::Key::L,
                                    'm' => egui::Key::M, 'n' => egui::Key::N, 'o' => egui::Key::O,
                                    'p' => egui::Key::P, 'q' => egui::Key::Q, 'r' => egui::Key::R,
                                    's' => egui::Key::S, 't' => egui::Key::T, 'u' => egui::Key::U,
                                    'v' => egui::Key::V, 'w' => egui::Key::W, 'x' => egui::Key::X,
                                    'y' => egui::Key::Y, 'z' => egui::Key::Z,
                                    _ => continue,
                                };
                                if ctx.input(|i| i.key_pressed(key)) {
                                    let upper = ch.to_ascii_uppercase();
                                    scroll_target = self
                                        .xml_files
                                        .iter()
                                        .find(|f| f.to_ascii_uppercase().starts_with(upper))
                                        .cloned();
                                    if scroll_target.is_some() {
                                        break;
                                    }
                                }
                            }
                            // 列表项由 ComboBox 自带的 ScrollArea 承载
                            // 字母键命中后滚动到对应项（不改变选中项）
                            let mut scrolled = false;
                            for f in &self.xml_files {
                                let resp = ui.selectable_value(
                                    &mut self.selected_file,
                                    Some(f.clone()),
                                    f,
                                );
                                if let Some(t) = &scroll_target {
                                    if !scrolled && f == t {
                                        scrolled = true;
                                        resp.scroll_to_me(Some(egui::Align::Center));
                                    }
                                }
                            }
                        });
                    if self.selected_file != prev {
                        self.load_selected();
                    }

                    ui.add_space(6.0);
                    ui.separator();
                    ui.add_space(6.0);

                    // 统计
                    if !self.entries.is_empty() {
                        let total = self.entries.len();
                        let done = self.translated_count();
                        let pct = if total > 0 {
                            (done as f32 / total as f32 * 100.0) as i32
                        } else {
                            0
                        };
                        egui::Frame::default()
                            .fill(C_ACCENT_LIGHT)
                            .inner_margin(egui::Margin::symmetric(6, 4))
                            .stroke(egui::Stroke::new(1.0, C_ACCENT))
                            .show(ui, |ui| {
                                ui.with_layout(egui::Layout::left_to_right(egui::Align::Center), |ui| {
                                    ui.label(
                                        egui::RichText::new(format!("{done}/{total}"))
                                            .size(14.0)
                                            .color(C_ACCENT)
                                            .strong(),
                                    );
                                    ui.add_space(4.0);
                                    ui.label(
                                        egui::RichText::new(format!("({pct}%)"))
                                            .size(10.0)
                                            .color(C_TEXT_MUTED),
                                    );
                                });
                            });
                    }

                    ui.add_space(6.0);
                    ui.separator();
                    ui.add_space(6.0);

                    // 操作按钮组（全部居中对齐）
                    let has_xml = self.selected_file.is_some() && !self.entries.is_empty();

                    // 置顶、还原
                    if ui.add_enabled(has_xml, egui::Button::new("📌 置顶")).clicked() {
                        self.pin_up();
                    }
                    ui.add_space(4.0);
                    if ui.add_enabled(has_xml, egui::Button::new("↩ 还原")).clicked() {
                        self.restore_order();
                    }
                    ui.add_space(8.0);

                    // 分隔线
                    ui.separator();
                    ui.add_space(6.0);

                    // 导入 mess.lst
                    if ui.add_enabled(has_xml, egui::Button::new("📥 导入 mess.lst")).clicked() {
                        self.preview_import();
                        self.confirm_import = true;
                    }
                    ui.add_space(4.0);

                    // 导出 mess.lst
                    if ui.add_enabled(has_xml, egui::Button::new("📤 导出 mess.lst")).clicked() {
                        self.preview_export();
                        self.confirm_export = true;
                    }
                    ui.add_space(8.0);

                    // 分隔组 + 写入 XML（最右侧，主操作强调色）
                    ui.separator();
                    ui.add_space(6.0);

                    // 写入XML（蓝色强调按钮，无 XML 时禁用）
                    let mut clicked_write = false;
                    ui.add_enabled_ui(has_xml, |ui| {
                        clicked_write = btn_style(ui, "💾 写入 XML", false).clicked();
                    });
                    if clicked_write {
                            self.confirm_write = true;
                        }

                        // 右侧分割线 + 关于
                        ui.add_space(6.0);
                        ui.separator();
                        ui.add_space(6.0);
                        if ui
                            .add(
                                egui::Button::new(egui::RichText::new("关于").color(C_TEXT))
                                    .fill(egui::Color32::from_rgb(245, 245, 245))
                                    .stroke(egui::Stroke::new(1.0, C_BORDER)),
                            )
                            .clicked()
                        {
                            self.show_about_dialog = true;
                        }
                    });
                });
            });

        // ============================================================
        // 中央表格 — 专业级美化
        // ============================================================
        egui::CentralPanel::default()
            .frame(
                egui::Frame::default()
                    .fill(C_BG)
                    .inner_margin(egui::Margin::same(0)),
            )
            .show(ui, |ui| {
                if self.entries.is_empty() {
                    ui.centered_and_justified(|ui| {
                        ui.vertical(|ui| {
                            ui.label(
                                egui::RichText::new("📂")
                                    .size(48.0)
                                    .color(C_TEXT_MUTED),
                            );
                            ui.add_space(10.0);
                            if self.xml_files.is_empty() {
                                ui.label(
                                    egui::RichText::new("请将程序放在包含 hash/ 文件夹的目录下")
                                        .size(14.0)
                                        .color(C_TEXT_SEC),
                                );
                                ui.add_space(4.0);
                                ui.label(
                                    egui::RichText::new("hash/ 文件夹中应包含 MAME 的 XML 软件列表")
                                        .size(12.0)
                                        .color(C_TEXT_MUTED),
                                );
                            } else {
                                ui.label(
                                    egui::RichText::new("请在顶部选择一个 XML 列表以开始汉化")
                                        .size(14.0)
                                        .color(C_TEXT_SEC),
                                );
                            }
                        });
                    });
                    return;
                }

                let order = self.display_order.clone();

                // ============================================================
                // 手写三列表格 — 生产级样式（斑马纹 / hover / 虚拟滚动）
                // ============================================================
                let avail = ui.available_width();
                let col_name = 190.0_f32.min(avail * 0.20).max(150.0);
                let col_trans = 400.0_f32.min(avail * 0.38).max(300.0);
                let col_desc = (avail - col_name - col_trans - 36.0).max(240.0);
                let row_h = 38.0_f32;
                let hdr_font = egui::FontId::proportional(14.0);

                // ---- 表头（网格线风格）----
                let (hdr_rect, _) = ui.allocate_exact_size(egui::vec2(avail, row_h), egui::Sense::hover());
                // 表头边框
                ui.painter().rect_stroke(hdr_rect, 0.0, egui::Stroke::new(1.0, C_BORDER_STRONG), egui::StrokeKind::Middle);
                // 列分隔竖线
                let x1 = hdr_rect.left() + col_name;
                let x2 = hdr_rect.left() + col_name + col_desc;
                ui.painter().line_segment(
                    [egui::pos2(x1, hdr_rect.top()), egui::pos2(x1, hdr_rect.bottom())],
                    egui::Stroke::new(1.0, C_BORDER),
                );
                ui.painter().line_segment(
                    [egui::pos2(x2, hdr_rect.top()), egui::pos2(x2, hdr_rect.bottom())],
                    egui::Stroke::new(1.0, C_BORDER),
                );
                ui.painter().text(
                    hdr_rect.left_center() + egui::vec2(30.0, 0.0),
                    egui::Align2::LEFT_CENTER,
                    "Name",
                    hdr_font.clone(),
                    C_TEXT,
                );
                ui.painter().text(
                    hdr_rect.left_center() + egui::vec2(col_name + 14.0, 0.0),
                    egui::Align2::LEFT_CENTER,
                    "Description",
                    hdr_font.clone(),
                    C_TEXT,
                );
                ui.painter().text(
                    hdr_rect.left_center() + egui::vec2(col_name + col_desc + 16.0, 0.0),
                    egui::Align2::LEFT_CENTER,
                    "Rename",
                    hdr_font.clone(),
                    C_TEXT,
                );

                // ---- 数据行（虚拟滚动，仅渲染可见行） ----
                egui::ScrollArea::vertical()
                    .auto_shrink(false)
                    .show_rows(ui, row_h, order.len(), |ui, range| {
                        let row_w = ui.available_width();
                        for ri in range {
                            let idx = order[ri];
                            let (orig_idx, entry) = &mut self.entries[idx];
                            let is_t = !entry.translation.trim().is_empty();

                            let (row_rect, resp) =
                                ui.allocate_exact_size(egui::vec2(row_w, row_h), egui::Sense::hover());

                            // 行背景：斑马纹 + hover 高亮（在边框下方）
                            let bg = if resp.hovered() {
                                C_ACCENT_LIGHT
                            } else if ri % 2 == 0 {
                                C_BG_PANEL
                            } else {
                                C_BG_ROW_B
                            };
                            // 绘制背景时略缩 1px，不遮挡网格线
                            let bg_rect = row_rect.shrink(1.0);
                            ui.painter().rect_filled(bg_rect, egui::CornerRadius::ZERO, bg);
                            // 行边框（网格线）
                            ui.painter().rect_stroke(row_rect, 0.0, egui::Stroke::new(1.0, C_BORDER), egui::StrokeKind::Middle);
                            // 列分隔竖线
                            let x1 = row_rect.left() + col_name;
                            let x2 = row_rect.left() + col_name + col_desc;
                            ui.painter().line_segment(
                                [egui::pos2(x1, row_rect.top()), egui::pos2(x1, row_rect.bottom())],
                                egui::Stroke::new(1.0, C_BORDER),
                            );
                            ui.painter().line_segment(
                                [egui::pos2(x2, row_rect.top()), egui::pos2(x2, row_rect.bottom())],
                                egui::Stroke::new(1.0, C_BORDER),
                            );

                            // 第一列：状态圆点 + Name（可复制文本）
                            let marker_color = if is_t { C_SUCCESS } else { C_WARNING };
                            let name_color = if is_t { C_SUCCESS } else { C_TEXT };
                            ui.painter().text(
                                row_rect.left_center() + egui::vec2(16.0, 0.0),
                                egui::Align2::LEFT_CENTER,
                                "●",
                                egui::FontId::proportional(11.0),
                                marker_color,
                            );
                            let name_rect = egui::Rect::from_min_max(
                                egui::pos2(row_rect.left() + 30.0, row_rect.top()),
                                egui::pos2(row_rect.left() + col_name - 8.0, row_rect.bottom()),
                            );
                            put_left(
                                ui,
                                name_rect,
                                egui::Label::new(
                                    egui::RichText::new(&entry.name)
                                        .size(13.0)
                                        .color(name_color)
                                        .monospace(),
                                )
                                .selectable(true)
                                .truncate()
                                .halign(egui::Align::LEFT),
                            );

                            // 第二列：Description（可复制文本，不可编辑，无悬停提示）
                            let desc_rect = egui::Rect::from_min_max(
                                egui::pos2(row_rect.left() + col_name + 12.0, row_rect.top()),
                                egui::pos2(
                                    row_rect.left() + col_name + col_desc - 8.0,
                                    row_rect.bottom(),
                                ),
                            );
                            put_left(
                                ui,
                                desc_rect,
                                egui::Label::new(
                                    egui::RichText::new(&entry.description)
                                        .size(11.5)
                                        .color(C_TEXT_SEC),
                                )
                                .selectable(true)
                                .truncate()
                                .halign(egui::Align::LEFT),
                            );

                            // 第三列：汉化输入框（单层边框 + 白底 + 圆角）
                            let te_rect = egui::Rect::from_min_max(
                                egui::pos2(
                                    row_rect.left() + col_name + col_desc + 10.0,
                                    row_rect.top() + 3.0,
                                ),
                                egui::pos2(
                                    row_rect.left() + col_name + col_desc + col_trans - 8.0,
                                    row_rect.bottom() - 3.0,
                                ),
                            );
                            let te_stroke_color = if is_t { C_SUCCESS } else { C_BORDER_STRONG };
                            let te_stroke_w = if is_t { 1.5_f32 } else { 1.0 };
                            let te_bg = if is_t { C_SUCCESS_LIGHT } else { egui::Color32::WHITE };
                            let te_frame = egui::Frame::default()
                                .fill(te_bg)
                                .stroke(egui::Stroke::new(te_stroke_w, te_stroke_color))
                                .inner_margin(4.0)
                                .corner_radius(3.0);
                            ui.put(
                                te_rect,
                                egui::TextEdit::singleline(&mut entry.translation)
                                    .text_color(if is_t { C_SUCCESS } else { C_TEXT })
                                    .hint_text(egui::RichText::new("输入中文描述…").color(C_TEXT_MUTED).size(13.0))
                                    .background_color(egui::Color32::TRANSPARENT)
                                    .font(egui::FontId::proportional(14.0))
                                    .vertical_align(egui::Align::Center)
                                    .frame(te_frame),
                            );
                            let _ = orig_idx;
                        }
                    });
            });

        // ============================================================
        // 底部状态栏 — 现代风格
        // ============================================================
        egui::Panel::bottom("statusbar")
            .frame(
                egui::Frame::default()
                    .fill(if self.status_ok { C_STATUS_OK_BG } else { C_STATUS_ERR_BG })
                    .inner_margin(egui::Margin::symmetric(14, 8))
                    .stroke(egui::Stroke::new(1.0, C_BORDER)),
            )
            .show(ui, |ui| {
                ui.with_layout(egui::Layout::left_to_right(egui::Align::Center), |ui| {
                    let status_color = if self.status_ok { C_SUCCESS } else { C_DANGER };
                    // 状态指示圆点
                    ui.painter().circle_filled(
                        ui.cursor().center_top() + egui::vec2(5.0, 0.0),
                        5.0,
                        status_color,
                    );
                    ui.add_space(14.0);
                    ui.label(
                        egui::RichText::new(&self.status_msg)
                            .size(12.0)
                            .color(if self.status_ok { C_SUCCESS } else { C_DANGER })
                            .strong(),
                    );
                });
            });

        // ============================================================
        // 写入确认对话框
        // ============================================================
        if self.confirm_write {
            let count = self.translated_count();
            let total = self.entries.len();
            let file = self.selected_file.clone().unwrap_or_default();

            let resp = egui::Modal::new(egui::Id::new("dlg_write"))
                .frame(dialog_frame())
                .show(ui.ctx(), |ui| {
                    ui.set_width(404.0);
                    dialog_header(
                        ui,
                        "💾",
                        C_ACCENT_LIGHT,
                        C_ACCENT,
                        "写入 XML",
                        "把 Rename 列的内容写回源文件",
                    );

                    ui.add_space(18.0);

                    ui.with_layout(egui::Layout::top_down_justified(egui::Align::Min), |ui| {
                        // 信息卡片
                        dialog_card(egui::Color32::from_rgb(250, 250, 252), Some(C_BORDER)).show(
                            ui,
                            |ui| {
                                kv_row(ui, "目标文件", &file, C_TEXT);
                                kv_row(ui, "写入条目", &format!("{count} 条"), C_ACCENT);
                                kv_row(ui, "写入字段", "description", C_TEXT);
                                ui.add_space(6.0);
                                progress_bar(ui, count, total, C_ACCENT);
                            },
                        );

                        ui.add_space(12.0);

                        notice_bar(
                            ui,
                            "⚠",
                            "将直接修改 XML 源文件且不可撤销，建议先导出 mess.lst 备份。",
                            C_DANGER_LIGHT,
                            C_DANGER,
                        );

                        ui.add_space(16.0);

                        dialog_buttons(
                            ui,
                            Some(("确认写入", BtnKind::Danger)),
                            count > 0,
                            "取消",
                        )
                    })
                });

            match resp.inner.inner {
                DialogAction::Primary => {
                    self.write_back();
                    self.confirm_write = false;
                }
                DialogAction::Secondary => self.confirm_write = false,
                DialogAction::None => {
                    if resp.should_close() {
                        self.confirm_write = false;
                    }
                }
            }
        }

        // ============================================================
        // 导入 mess.lst 确认对话框
        // ============================================================
        if self.confirm_import {
            let file = self.selected_file.clone().unwrap_or_default();
            let lst = self.mess_lst_path.clone();
            let matched = self.import_preview;
            let blanks = self.untranslated_count();
            let exists = std::path::Path::new(&lst).exists();

            let resp = egui::Modal::new(egui::Id::new("dlg_import"))
                .frame(dialog_frame())
                .show(ui.ctx(), |ui| {
                    ui.set_width(404.0);
                    dialog_header(
                        ui,
                        "📥",
                        C_ACCENT_LIGHT,
                        C_ACCENT,
                        "导入 mess.lst",
                        "用公共汉化列表填充空白条目",
                    );

                    ui.add_space(18.0);

                    ui.with_layout(egui::Layout::top_down_justified(egui::Align::Min), |ui| {
                        dialog_card(egui::Color32::from_rgb(250, 250, 252), Some(C_BORDER)).show(
                            ui,
                            |ui| {
                                kv_row(
                                    ui,
                                    "来源文件",
                                    if exists { &lst } else { "（文件不存在）" },
                                    if exists { C_TEXT } else { C_DANGER },
                                );
                                kv_row(ui, "当前列表", &file, C_TEXT);
                                kv_row(ui, "可导入", &format!("{matched} 条"), C_SUCCESS);
                                kv_row(ui, "空白条目", &format!("{blanks} 条"), C_TEXT_SEC);
                            },
                        );

                        ui.add_space(12.0);

                        notice_bar(
                            ui,
                            "ℹ",
                            "仅填充 Rename 为空的条目，已有汉化不会被覆盖。",
                            C_ACCENT_LIGHT,
                            C_ACCENT,
                        );

                        ui.add_space(16.0);

                        dialog_buttons(
                            ui,
                            Some(("开始导入", BtnKind::Primary)),
                            matched > 0 && exists,
                            "取消",
                        )
                    })
                });

            match resp.inner.inner {
                DialogAction::Primary => {
                    self.import_mess_lst();
                    self.confirm_import = false;
                }
                DialogAction::Secondary => self.confirm_import = false,
                DialogAction::None => {
                    if resp.should_close() {
                        self.confirm_import = false;
                    }
                }
            }
        }

        // ============================================================
        // 导出 mess.lst 确认对话框
        // ============================================================
        if self.confirm_export {
            let file = self.selected_file.clone().unwrap_or_default();
            let lst = self.mess_lst_path.clone();
            let count = self.export_preview;
            let total_in_list = self.lst_total;
            let stem = file.strip_suffix(".xml").unwrap_or(&file);
            let prefix = format!("{stem}__");

            let resp = egui::Modal::new(egui::Id::new("dlg_export"))
                .frame(dialog_frame())
                .show(ui.ctx(), |ui| {
                    ui.set_width(404.0);
                    dialog_header(
                        ui,
                        "📤",
                        C_ACCENT_LIGHT,
                        C_ACCENT,
                        "导出 mess.lst",
                        "把当前汉化并入公共列表",
                    );

                    ui.add_space(18.0);

                    ui.with_layout(egui::Layout::top_down_justified(egui::Align::Min), |ui| {
                        dialog_card(egui::Color32::from_rgb(250, 250, 252), Some(C_BORDER)).show(
                            ui,
                            |ui| {
                                kv_row(ui, "目标文件", &lst, C_TEXT);
                                kv_row(ui, "当前列表", &file, C_TEXT);
                                kv_row(ui, "将导出", &format!("{count} 条"), C_ACCENT);
                                kv_row(
                                    ui,
                                    "列表现有",
                                    &format!("{total_in_list} 条"),
                                    C_TEXT_SEC,
                                );
                            },
                        );

                        ui.add_space(12.0);

                        notice_bar(
                            ui,
                            "ℹ",
                            &format!("同前缀 {prefix} 的旧条目会被本次导出替换。"),
                            C_WARNING_LIGHT,
                            C_WARNING,
                        );

                        ui.add_space(16.0);

                        dialog_buttons(
                            ui,
                            Some(("确认导出", BtnKind::Primary)),
                            count > 0,
                            "取消",
                        )
                    })
                });

            match resp.inner.inner {
                DialogAction::Primary => {
                    self.export_mess_lst();
                    self.confirm_export = false;
                }
                DialogAction::Secondary => self.confirm_export = false,
                DialogAction::None => {
                    if resp.should_close() {
                        self.confirm_export = false;
                    }
                }
            }
        }

        // ============================================================
        // 操作结果弹窗（导入/导出/写入的结果通知）
        // ============================================================
        if let Some((msg, ok)) = self.show_result_dialog.clone() {
            let result_color = if ok { C_SUCCESS } else { C_DANGER };
            let result_bg = if ok { C_SUCCESS_LIGHT } else { C_DANGER_LIGHT };

            let resp = egui::Modal::new(egui::Id::new("dlg_result"))
                .frame(dialog_frame())
                .show(ui.ctx(), |ui| {
                    ui.set_width(360.0);
                    dialog_header(
                        ui,
                        if ok { "✔" } else { "✖" },
                        result_bg,
                        result_color,
                        if ok { "操作成功" } else { "操作失败" },
                        "",
                    );

                    ui.add_space(18.0);

                    ui.with_layout(egui::Layout::top_down_justified(egui::Align::Min), |ui| {
                        dialog_card(egui::Color32::from_rgb(250, 250, 252), Some(C_BORDER)).show(
                            ui,
                            |ui| {
                                ui.add(
                                    egui::Label::new(egui::RichText::new(&msg).size(13.0))
                                        .wrap(),
                                );
                            },
                        );

                        ui.add_space(16.0);

                        dialog_buttons(ui, Some(("确定", BtnKind::Primary)), true, "")
                    })
                });

            if resp.inner.inner == DialogAction::Primary || resp.should_close() {
                self.show_result_dialog = None;
            }
        }

        // ============================================================
        // 关于窗口
        // ============================================================
        if self.show_about_dialog {
            let resp = egui::Modal::new(egui::Id::new("dlg_about"))
                .frame(dialog_frame())
                .show(ui.ctx(), |ui| {
                    ui.set_width(384.0);

                    ui.vertical_centered(|ui| {
                        let (rect, _) =
                            ui.allocate_exact_size(egui::vec2(52.0, 52.0), egui::Sense::hover());
                        ui.painter().circle_filled(rect.center(), 26.0, C_ACCENT_LIGHT);
                        ui.painter().text(
                            rect.center(),
                            egui::Align2::CENTER_CENTER,
                            "ℹ",
                            egui::FontId::proportional(26.0),
                            C_ACCENT,
                        );
                        ui.add_space(10.0);
                        ui.label(
                            egui::RichText::new("MessGameList")
                                .size(18.0)
                                .color(C_TEXT)
                                .strong(),
                        );
                        ui.label(egui::RichText::new("v1.0").size(12.5).color(C_TEXT_SEC));
                    });

                    ui.add_space(18.0);

                    ui.with_layout(egui::Layout::top_down_justified(egui::Align::Min), |ui| {
                        dialog_card(egui::Color32::from_rgb(250, 250, 252), Some(C_BORDER)).show(
                            ui,
                            |ui| {
                                ui.horizontal(|ui| {
                                    ui.add(egui::Label::new(
                                        egui::RichText::new("联系方式").size(12.5).color(C_TEXT_SEC),
                                    ));
                                    ui.add_space(10.0);
                                    ui.add(egui::Label::new(
                                        egui::RichText::new("公众号：红白机时空舱")
                                            .size(14.0)
                                            .color(C_ACCENT)
                                            .strong(),
                                    ));
                                });
                                ui.add_space(8.0);
                                ui.add(
                                    egui::Label::new(
                                        egui::RichText::new(
                                            "如有任何问题，请通过公众号与我私信联系，看到后将第一时间答复。",
                                        )
                                        .size(12.5)
                                        .color(C_TEXT_SEC),
                                    )
                                    .wrap(),
                                );
                            },
                        );

                        ui.add_space(16.0);

                        dialog_buttons(ui, Some(("确定", BtnKind::Primary)), true, "")
                    })
                });

            if resp.inner.inner == DialogAction::Primary || resp.should_close() {
                self.show_about_dialog = false;
            }
        }
    }
}

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1280.0, 780.0])
            .with_min_inner_size([860.0, 540.0])
            .with_title("MessGameList"),
        ..Default::default()
    };
    eframe::run_native(
        "MessGameList",
        options,
        Box::new(|cc| {
            App::install_fonts(&cc.egui_ctx);
            Ok(Box::new(App::new()))
        }),
    )
}
