#!/usr/bin/env python3
"""章节脚手架脚本 —— scripts/scaffold_section.py

用法:
    python scripts/scaffold_section.py <物料包 yaml> [--out <输出目录>]

作用：
    根据物料包 yaml，生成一份"填空脚手架" markdown，含：
    - YAML frontmatter（已填好元数据）
    - 十二段空标题（已按规范排好顺序）
    - 每段下方给出该段的「填空提示」（来自物料包的 section_outline）
    - 关键字段（必含关键词、最小字数、模板编号）作为 HTML 注释嵌入
    - 已有的 code_snippets 直接插入到 §8
    - 推荐的 mermaid_templates 已渲染为占位代码块

中等模型拿到这份脚手架后，**只需填入每段的中文内容**，禁止：
- 修改标题层级与顺序
- 删除 HTML 注释中的约束提示
- 修改已插入的 code_snippets

输出：
    默认 doc/学习资料_v2/<章目录>/<节文件>.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，章节/物料包路径含中文会触发 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    print("ERROR: 请先 pip install pyyaml", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent


SECTION_SPEC = [
    # (段标题, outline key, 默认提示)
    ("学习目标", "s02_objectives", "用「读完本节，你能：」开头，至少 3 条可验证目标"),
    ("前置知识", "s03_prereq", "列出读者需先掌握的章节与概念"),
    ("场景故事（车载视角）", "s04_scene", "200 字以上的具体车机场景"),
    ("协议正文 / 概念深入", "s05_protocol",
     "600 字以上，含 Spec 章节号 + 帧结构 + 时序参数"),
    ("分层调用链", "s06_call_chain", "至少 4 层，每层 1 行 'X → Y' + file:line"),
    ("源码导读", "s07_source_guide",
     "至少 6 个 file:line，按推荐阅读顺序排列，每条说明'为什么读'"),
    ("简化代码片段", "s08_simplified_code", "至少 2 段，直接来自物料包 code_snippets"),
    ("流程图 / 时序图", "s09_mermaid",
     "至少 2 张 Mermaid 图，使用物料包 mermaid_templates 推荐模板"),
    ("实测数据", "s10_measured", "时延 / 成功率 / 重试次数（含具体数字）"),
    ("调试方法 / 车机集成点", "s11_debug",
     "调试方法（logcat/dumpsys/btsnoop/aconfig） + 车机集成点（OEM 定制位置）"),
    ("FAQ + 自测题 + 上路任务", "s12_faq_homework", "FAQ ≥ 3 / 自测题 ≥ 3 / 上路任务 ≥ 2"),
]


def fmt_constraint(outline_entry: dict | None) -> str:
    """把 section_outline 中一段的字段渲染成 HTML 注释约束"""
    if not outline_entry:
        return ""
    lines = ["<!-- 约束 -->"]
    if "min_words" in outline_entry:
        lines.append(f"<!--   最小字数: {outline_entry['min_words']} -->")
    if "must_contain" in outline_entry:
        for kw in outline_entry["must_contain"]:
            lines.append(f"<!--   必含关键词: {kw} -->")
    if "must_mention" in outline_entry:
        for kw in outline_entry["must_mention"]:
            lines.append(f"<!--   必提及: {kw} -->")
    if "must_link" in outline_entry:
        for ln in outline_entry["must_link"]:
            lines.append(f"<!--   必交叉链接: {ln} -->")
    if "must_have_hexdump" in outline_entry and outline_entry["must_have_hexdump"]:
        lines.append("<!--   必含协议帧 hexdump -->")
    if "min_layers" in outline_entry:
        lines.append(f"<!--   最少分层: {outline_entry['min_layers']} -->")
    if "format" in outline_entry:
        lines.append(f"<!--   格式提示: {outline_entry['format'].strip()} -->")
    if "min_refs" in outline_entry:
        lines.append(f"<!--   最少 file:line 引用: {outline_entry['min_refs']} -->")
    if "all_from_allowed_refs" in outline_entry:
        lines.append("<!--   所有引用必须来自物料包 allowed_refs -->")
    if "suggested_order" in outline_entry:
        lines.append("<!--   建议阅读顺序: -->")
        for o in outline_entry["suggested_order"]:
            lines.append(f"<!--     - {o} -->")
    if "min_snippets" in outline_entry:
        lines.append(f"<!--   最少代码片段: {outline_entry['min_snippets']} -->")
    if "required_snippets" in outline_entry:
        lines.append(f"<!--   必含片段 id: {outline_entry['required_snippets']} -->")
    if "min_diagrams" in outline_entry:
        lines.append(f"<!--   最少 Mermaid 图: {outline_entry['min_diagrams']} -->")
    if "required_templates" in outline_entry:
        lines.append(f"<!--   必用模板编号: {outline_entry['required_templates']} -->")
    if "required_fields" in outline_entry:
        lines.append("<!--   必含字段: -->")
        for f in outline_entry["required_fields"]:
            lines.append(f"<!--     - {f} -->")
    if "data_source_hint" in outline_entry:
        lines.append(f"<!--   数据来源建议: {outline_entry['data_source_hint']} -->")
    if "must_include_commands" in outline_entry:
        lines.append("<!--   必含命令: -->")
        for c in outline_entry["must_include_commands"]:
            lines.append(f"<!--     - {c} -->")
    if "car_integration_points" in outline_entry:
        lines.append("<!--   车机集成点提示: -->")
        for c in outline_entry["car_integration_points"]:
            lines.append(f"<!--     - {c} -->")
    if "min_faqs" in outline_entry:
        lines.append(f"<!--   最少 FAQ: {outline_entry['min_faqs']} -->")
    if "min_quizzes" in outline_entry:
        lines.append(f"<!--   最少自测题: {outline_entry['min_quizzes']} -->")
    if "min_homeworks" in outline_entry:
        lines.append(f"<!--   最少上路任务: {outline_entry['min_homeworks']} -->")
    if "suggested_faqs" in outline_entry:
        lines.append("<!--   建议 FAQ 题目: -->")
        for q in outline_entry["suggested_faqs"]:
            lines.append(f"<!--     - {q} -->")
    if "suggested_homeworks" in outline_entry:
        lines.append("<!--   建议上路任务: -->")
        for h in outline_entry["suggested_homeworks"]:
            lines.append(f"<!--     - {h} -->")
    if "template" in outline_entry:
        lines.append("<!--   模板提示: -->")
        for ln in outline_entry["template"].strip().splitlines():
            lines.append(f"<!--     {ln} -->")
    if "template_hint" in outline_entry:
        lines.append("<!--   场景模板: -->")
        for ln in outline_entry["template_hint"].strip().splitlines():
            lines.append(f"<!--     {ln} -->")
    return "\n".join(lines)


def render_snippet(snip: dict) -> str:
    """渲染一个 code_snippets 条目为 markdown 代码块"""
    lang = snip.get("language", "cpp")
    source = snip.get("source", "")
    code = snip.get("code", "").rstrip()
    annotation = snip.get("annotation", "").strip()
    parts = [
        f"**来源**：`{source}`",
        "",
        f"```{lang}",
        code,
        "```",
    ]
    if annotation:
        parts += ["", annotation]
    return "\n".join(parts)


def render_mermaid_placeholder(t: dict) -> str:
    tid = t.get("id", "T-???")
    use = t.get("use_for", "<待填写：本图展示什么>")
    return (
        f"<!-- 模板编号: {tid} | 用途: {use} -->\n"
        f"<!-- 请从 doc/v2_Mermaid模板库.md 复制 {tid} 的源码，替换占位符 -->\n"
        "```mermaid\n"
        "%% TODO: 用 " + tid + " 模板填空\n"
        "```"
    )


def render_pitfalls(pitfalls: list[dict]) -> str:
    if not pitfalls:
        return ""
    lines = ["<!--", "已知陷阱（生成时必须注意）："]
    for p in pitfalls:
        lines.append(f"  - {p.get('description', '')}")
        if p.get("detail"):
            lines.append(f"      {p['detail']}")
    lines.append("-->")
    return "\n".join(lines)


def render_terms(terms: list[dict]) -> str:
    if not terms:
        return ""
    lines = ["<!--", "术语约束（必须遵守）："]
    for t in terms:
        canon = t.get("canonical", "")
        forbidden = t.get("forbidden", []) or []
        lines.append(f"  - 规范译名: {canon}")
        if forbidden:
            lines.append(f"      禁用: {forbidden}")
    lines.append("-->")
    return "\n".join(lines)


def render_cross_links(links: list[dict]) -> str:
    if not links:
        return ""
    lines = ["<!--", "建议交叉链接（应在合适位置嵌入）："]
    for ln in links:
        target = ln.get("target", "")
        anchor = ln.get("anchor_text", "")
        lines.append(f"  - {anchor} → {target}")
    lines.append("-->")
    return "\n".join(lines)


def build_scaffold(data: dict) -> str:
    meta = data.get("meta", {})
    sid = meta.get("section_id", "?.?")
    title = meta.get("title", "<标题>")

    outline = data.get("section_outline", {}) or {}
    snippets = {s.get("id"): s for s in (data.get("code_snippets") or [])}
    templates = data.get("mermaid_templates") or []

    parts: list[str] = []

    # YAML frontmatter
    fm = {
        "section_id": sid,
        "title": title,
        "priority": meta.get("priority", "P2"),
        "audience": meta.get("audience", []),
        "prerequisites": meta.get("prerequisites", []),
        "related": meta.get("related_sections", []),
        "estimated_reading_min": meta.get("estimated_reading_min", 30),
        "estimated_practice_min": meta.get("estimated_practice_min", 60),
        "last_verified": str(meta.get("last_verified", "")),
        "verified_against_aosp": meta.get("verified_against_aosp", ""),
    }
    parts.append("---")
    parts.append(yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip())
    parts.append("---")
    parts.append("")

    # 标题
    parts.append(f"# {sid} {title}")
    parts.append("")

    # 全局约束注释（术语/陷阱/链接）
    terms_block = render_terms(data.get("terms") or [])
    pitfalls_block = render_pitfalls(data.get("known_pitfalls") or [])
    links_block = render_cross_links(data.get("cross_links") or [])
    for block in (terms_block, pitfalls_block, links_block):
        if block:
            parts.append(block)
            parts.append("")

    # 速通摘要
    parts.append("> **速通摘要**：<!-- 3-5 句，说清本节讲什么 / 为什么重要 / 关键产出 -->")
    parts.append("")

    # 十二段
    for title_zh, key, default_hint in SECTION_SPEC:
        parts.append(f"## {title_zh}")
        parts.append("")
        constraint = fmt_constraint(outline.get(key))
        if constraint:
            parts.append(constraint)
            parts.append("")
        else:
            parts.append(f"<!-- 提示: {default_hint} -->")
            parts.append("")

        # 特殊段：§8 自动插入代码片段，§9 自动插入 Mermaid 占位
        if key == "s08_simplified_code":
            required = (outline.get(key, {}) or {}).get("required_snippets") or list(snippets.keys())
            for sid_req in required:
                snip = snippets.get(sid_req)
                if snip:
                    parts.append(f"### 片段：{sid_req}")
                    parts.append("")
                    parts.append(render_snippet(snip))
                    parts.append("")
        elif key == "s09_mermaid":
            for t in templates:
                parts.append(render_mermaid_placeholder(t))
                parts.append("")

        parts.append("<!-- ↑ 在此段下方填写中文内容 -->")
        parts.append("")

    return "\n".join(parts)


def derive_output_path(data: dict, out_dir: Path | None) -> Path:
    meta = data.get("meta", {})
    sid = meta.get("section_id", "0.0")
    title = meta.get("title", "untitled")

    # 主版本号决定章目录
    major = sid.split(".")[0]
    # 找现有 v2 章目录
    default_root = REPO_ROOT / "doc" / "学习资料_v2"
    if out_dir is None:
        out_dir = default_root

    # 优先用 v1 同章目录名
    v1_root = REPO_ROOT / "doc" / "学习资料"
    chapter_dir = None
    if v1_root.exists():
        for d in v1_root.iterdir():
            if d.is_dir() and d.name.startswith(f"{major}_"):
                chapter_dir = out_dir / d.name
                break
    if chapter_dir is None:
        # 用 物料包路径下的章名
        chapter_dir = out_dir / f"{major}_未命名"

    # 文件名
    safe_title = re.sub(r"[\s/\\:]", "_", title)
    return chapter_dir / f"{sid}_{safe_title}.md"


def main():
    parser = argparse.ArgumentParser(description="v2 章节脚手架脚本")
    parser.add_argument("materials", help="物料包 yaml 文件")
    parser.add_argument("--out", "-o", help="输出 md 路径或目录（默认 doc/学习资料_v2/）")
    parser.add_argument("--print", "-p", action="store_true", help="只打印不写入")
    args = parser.parse_args()

    mat_path = Path(args.materials)
    if not mat_path.exists():
        print(f"ERROR: 物料包不存在 {mat_path}", file=sys.stderr)
        sys.exit(2)

    try:
        data = yaml.safe_load(mat_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"ERROR: 物料包 YAML 解析失败 {e}", file=sys.stderr)
        sys.exit(2)

    scaffold = build_scaffold(data)

    if args.print:
        print(scaffold)
        return

    out = Path(args.out) if args.out else derive_output_path(data, None)
    if out.is_dir():
        out = derive_output_path(data, out)

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        print(f"WARN: 目标文件已存在，不覆盖: {out}", file=sys.stderr)
        print(f"      （如需覆盖，请先 rm '{out}' 或用 --out 指定新路径）", file=sys.stderr)
        sys.exit(1)

    out.write_text(scaffold, encoding="utf-8")
    print(f"✅ 脚手架已生成: {out}")
    print(f"   下一步：用中等模型按段填空，然后运行")
    print(f"           python scripts/verify_section.py '{out}' --materials '{mat_path}'")


if __name__ == "__main__":
    main()
