//! MAME MESS 软件列表汉化工具 - 核心逻辑
//!
//! 处理 XML 软件列表的解析与写回、mess.list 的读写。

use std::collections::HashMap;
use std::path::Path;

use encoding_rs;
use roxmltree::Document;

/// 单条软件条目
#[derive(Debug, Clone)]
pub struct Entry {
    /// software 节点的 name 属性
    pub name: String,
    /// 原始 description 文本
    pub description: String,
    /// 用户输入的汉化内容
    pub translation: String,
}

fn string_err<E: std::fmt::Display>(e: E) -> String {
    e.to_string()
}

/// roxmltree 节点范围兼容辅助（0.21 返回 Range<usize>）

/// 列出目录下所有 .xml 文件（按名称排序）
pub fn list_xml_files(dir: &str) -> Result<Vec<String>, String> {
    let mut files: Vec<String> = std::fs::read_dir(dir)
        .map_err(string_err)?
        .filter_map(|e| e.ok())
        .map(|e| e.file_name().to_string_lossy().into_owned())
        .filter(|f| f.to_lowercase().ends_with(".xml"))
        .collect();
    files.sort();
    Ok(files)
}

/// 解析 XML 软件列表文件，返回条目列表
/// 兼容 DTD 声明（MAME hash 文件常见 <!DOCTYPE …>）
pub fn parse_xml_file(path: &str) -> Result<Vec<Entry>, String> {
    let content = read_utf8_file(path)?;
    let opts = roxmltree::ParsingOptions {
        allow_dtd: true,
        ..Default::default()
    };
    let doc = Document::parse_with_options(&content, opts).map_err(string_err)?;

    let mut entries = Vec::new();
    for node in doc.descendants().filter(|n| n.has_tag_name("software")) {
        if let Some(name) = node.attribute("name") {
            let description = node
                .children()
                .find(|c| c.has_tag_name("description"))
                .and_then(|d| d.text())
                .unwrap_or("")
                .to_string();
            entries.push(Entry {
                name: name.to_string(),
                description,
                translation: String::new(),
            });
        }
    }
    Ok(entries)
}

/// XML 转义
pub fn escape_xml(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            _ => out.push(c),
        }
    }
    out
}

/// 把汉化内容写回 XML 文件。
///
/// `translations` 的 key 为 software 的 name 属性，value 为汉化文本。
/// 仅替换 `<description>` 节点的文本，保留文件其余字节不变。
/// 返回实际替换的条目数。
pub fn write_translations(path: &str, translations: &HashMap<String, String>) -> Result<usize, String> {
    let mut content = std::fs::read(path).map_err(string_err)?;
    let had_bom = content.starts_with(&[0xEF, 0xBB, 0xBF]);
    if had_bom {
        content.drain(..3);
    }
    let mut text = String::from_utf8(content).map_err(string_err)?;
    let opts = roxmltree::ParsingOptions {
        allow_dtd: true,
        ..Default::default()
    };
    let doc = Document::parse_with_options(&text, opts).map_err(string_err)?;

    // 收集 (起始偏移, 结束偏移, 新文本)，从后往前应用
    let mut replacements: Vec<(usize, usize, String)> = Vec::new();

    for node in doc.descendants().filter(|n| n.has_tag_name("software")) {
        let Some(name) = node.attribute("name") else { continue };
        let Some(new_text) = translations.get(name) else { continue };
        if new_text.is_empty() {
            continue;
        }
        let Some(desc) = node.children().find(|c| c.has_tag_name("description")) else {
            continue;
        };
        let range = desc.range();
        let escaped = escape_xml(new_text);
        replacements.push((range.start, range.end, format!("<description>{escaped}</description>")));
    }

    let replaced = replacements.len();
    replacements.sort_by_key(|r| std::cmp::Reverse(r.0));
    for (start, end, new) in replacements {
        text.replace_range(start..end, &new);
    }

    let mut out = Vec::with_capacity(text.len() + 3);
    if had_bom {
        out.extend_from_slice(&[0xEF, 0xBB, 0xBF]);
    }
    out.extend_from_slice(text.as_bytes());
    std::fs::write(path, out).map_err(string_err)?;

    Ok(replaced)
}

/// 判断字符串是否包含 CJK（中日韩汉字）字符
pub fn contains_cjk(s: &str) -> bool {
    s.chars().any(|c| {
        let u = c as u32;
        (0x4E00..=0x9FFF).contains(&u)      // CJK 统一表意文字
            || (0x3400..=0x4DBF).contains(&u)   // 扩展 A
            || (0xF900..=0xFAFF).contains(&u)   // 兼容表意文字
            || (0x20000..=0x2FA1F).contains(&u) // 扩展 B 及以后
    })
}

/// 清理可能破坏 mess.list 结构的字符（制表符/换行折叠为单个空格）
pub fn sanitize_field(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut pending_space = false;
    for c in s.chars() {
        if c == '\t' || c == '\r' || c == '\n' {
            pending_space = !out.is_empty();
        } else {
            if pending_space {
                out.push(' ');
                pending_space = false;
            }
            out.push(c);
        }
    }
    out
}

/// 读取文本文件：优先按 UTF-8（自动去 BOM），失败则按 GBK
pub fn read_text_file(path: &str) -> Result<String, String> {
    let bytes = std::fs::read(path).map_err(string_err)?;
    if let Ok(s) = String::from_utf8(bytes.clone()) {
        return Ok(s.trim_start_matches('\u{FEFF}').to_string());
    }
    // 尝试 GBK
    let (decoded, _, had_errors) = encoding_rs::GBK.decode(&bytes);
    if had_errors {
        Err("无法以 UTF-8 或 GBK 解码文件".to_string())
    } else {
        Ok(decoded.into_owned())
    }
}

fn read_utf8_file(path: &str) -> Result<String, String> {
    let bytes = std::fs::read(path).map_err(string_err)?;
    let content: &[u8] = if bytes.starts_with(&[0xEF, 0xBB, 0xBF]) {
        &bytes[3..]
    } else {
        &bytes
    };
    String::from_utf8(content.to_vec()).map_err(|e| format!("XML 必须为 UTF-8 编码: {e}"))
}

/// 读取 mess.list，返回 (第一列, 第二列) 列表。
/// 两列以制表符分割；跳过空行与不含制表符的行。优先 UTF-8，回退 GBK。
pub fn read_mess_list(path: &str) -> Result<Vec<(String, String)>, String> {
    let text = read_text_file(path)?;
    let mut out = Vec::new();
    for line in text.lines() {
        let line = line.trim_end_matches('\r');
        if line.trim().is_empty() {
            continue;
        }
        if let Some((k, v)) = line.split_once('\t') {
            out.push((k.trim().to_string(), v.trim().to_string()));
        }
        // 不含制表符的行跳过（如空行或注释）
    }
    Ok(out)
}

/// 写 mess.list（两列以制表符分割，UTF-8 编码）
pub fn write_mess_list(path: &str, items: &[(String, String)]) -> Result<(), String> {
    let mut out = String::new();
    for (k, v) in items {
        out.push_str(k);
        out.push('\t');
        out.push_str(v);
        out.push_str("\r\n");
    }
    std::fs::write(path, out.as_bytes()).map_err(string_err)
}

/// 由文件名（去掉 .xml 扩展名）与 name 属性生成 mess.list 第一列
/// 格式：stem__name（双下划线分隔）
pub fn make_key(file_name: &str, name: &str) -> String {
    let stem = file_name.strip_suffix(".xml").unwrap_or(file_name);
    format!("{stem}__{name}")
}

/// 兼容旧版单下划线无扩展名 key（导入时 fallback 用）
pub fn make_key_legacy(file_name: &str, name: &str) -> String {
    let stem = file_name.strip_suffix(".xml").unwrap_or(file_name);
    format!("{stem}_{name}")
}

/// 拼接目录与文件名
pub fn join_path(dir: &str, file: &str) -> String {
    Path::new(dir).join(file).to_string_lossy().into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE_XML: &str = r#"<?xml version="1.0"?>
<softwarelist name="a2600" description="Atari 2600 cartridges">
	<software name="adventp">
		<description>Adventure +</description>
		<year>2003</year>
	</software>
	<software name="ret2hh">
		<description>Return to Haunted House (Flashback 2)</description>
		<year>2005</year>
	</software>
	<software name="empty_desc">
		<description/>
		<year>1999</year>
	</software>
</softwarelist>
"#;

    #[test]
    fn parse_and_write_back() {
        let dir = std::env::temp_dir();
        let path = dir.join("mess_test_a2600.xml");
        std::fs::write(&path, SAMPLE_XML).unwrap();

        let entries = parse_xml_file(path.to_str().unwrap()).unwrap();
        assert_eq!(entries.len(), 3);
        assert_eq!(entries[0].name, "adventp");
        assert_eq!(entries[0].description, "Adventure +");

        // 写回汉化
        let mut map = HashMap::new();
        map.insert("adventp".to_string(), "冒险+".to_string());
        map.insert("ret2hh".to_string(), "重返鬼屋 (第二版)".to_string());
        map.insert("empty_desc".to_string(), "空描述 & 测试 <转义>".to_string());
        // 空文本不写回
        map.insert("adventp_empty_t".to_string(), String::new());
        let n = write_translations(path.to_str().unwrap(), &map).unwrap();
        assert_eq!(n, 3);

        let re_parsed = parse_xml_file(path.to_str().unwrap()).unwrap();
        assert_eq!(re_parsed[0].description, "冒险+");
        assert_eq!(re_parsed[1].description, "重返鬼屋 (第二版)");
        assert_eq!(re_parsed[2].description, "空描述 & 测试 <转义>");

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn mess_list_roundtrip() {
        let dir = std::env::temp_dir();
        let path = dir.join("mess_test.list");
        let items = vec![
            ("a2600__adventp".to_string(), "冒险+".to_string()),
            ("a2600__ret2hh".to_string(), "重返鬼屋 (第二版)".to_string()),
        ];
        write_mess_list(path.to_str().unwrap(), &items).unwrap();
        let read = read_mess_list(path.to_str().unwrap()).unwrap();
        assert_eq!(read, items);
        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn cjk_and_sanitize() {
        assert!(contains_cjk("冒险+"));
        assert!(!contains_cjk("Adventure +"));
        assert_eq!(sanitize_field("a\tb\r\nc"), "a b c");
    }
}
