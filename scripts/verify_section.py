#!/usr/bin/env python3
"""v2 章节自检脚本 —— scripts/verify_section.py

用法:
    python scripts/verify_section.py <章节 md 文件> [--materials <物料包 yaml>]

检查项（详见 doc/v2_编写规范.md §5）:
    1. 文件命名规范
    2. YAML frontmatter 必填字段
    3. 十二段标题齐全且顺序正确
    4. file:line 引用必须在物料包 allowed_refs 中
    5. file:line 引用必须实际可在仓库中 Grep 命中
    6. Mermaid 块数量 ≥ 2
    7. 各段字数下限
    8. 必含关键词
    9. 术语黑名单
    10. 调用链层数
    11. FAQ / 上路任务 / 自测题数量
    12. 实测数据关键字

返回值:
    0 = PASS
    1 = FAIL（阻断 commit）
    2 = WARN-only
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Windows 控制台默认 GBK，章节/物料包路径含中文会触发 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml  # PyYAML
except ImportError:
    print("ERROR: 请先 pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: str  # "FAIL" / "WARN"
    detail: str = ""


@dataclass
class Report:
    file: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def has_fail(self) -> bool:
        return any(not r.passed and r.severity == "FAIL" for r in self.results)

    @property
    def has_warn(self) -> bool:
        return any(not r.passed and r.severity == "WARN" for r in self.results)

    def add(self, name: str, passed: bool, severity: str = "FAIL", detail: str = ""):
        self.results.append(CheckResult(name, passed, severity, detail))

    def print_summary(self):
        print(f"\n=== Section Verify Report: {self.file} ===")
        for r in self.results:
            if r.passed:
                mark = "[OK]  "
            elif r.severity == "FAIL":
                mark = "[FAIL]"
            else:
                mark = "[WARN]"
            print(f"  {mark} {r.name}")
            if not r.passed and r.detail:
                for line in r.detail.splitlines():
                    print(f"        {line}")
        if self.has_fail:
            print("\nResult: FAIL (commit blocked)")
        elif self.has_warn:
            print("\nResult: WARN-only (allowed to commit, fix recommended)")
        else:
            print("\nResult: PASS")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

SECTION_TITLES = [
    # 段号: 正则模式（匹配一级标题文本）
    ("§2 学习目标", r"^##\s+(§2\s+)?学习目标"),
    ("§3 前置知识", r"^##\s+(§3\s+)?前置知识"),
    ("§4 场景故事", r"^##\s+(§4\s+)?场景故事"),
    ("§5 协议正文", r"^##\s+(§5\s+)?(协议正文|概念深入)"),
    ("§6 分层调用链", r"^##\s+(§6\s+)?分层调用链"),
    ("§7 源码导读", r"^##\s+(§7\s+)?源码导读"),
    ("§8 简化代码片段", r"^##\s+(§8\s+)?简化代码片段"),
    ("§9 流程图/时序图", r"^##\s+(§9\s+)?(流程图|时序图|Mermaid)"),
    ("§10 实测数据", r"^##\s+(§10\s+)?实测数据"),
    ("§11 调试方法/车机集成点", r"^##\s+(§11\s+)?(调试方法|车机集成)"),
    ("§12 FAQ/自测题/上路任务", r"^##\s+(§12\s+)?(FAQ|自测题|上路任务)"),
]

FILE_LINE_PATTERN = re.compile(
    r"`?([a-zA-Z0-9_./\-]+\.(?:cc|cpp|h|hpp|java|kt|aidl|py|sh|aconfig))(?::|#L)(\d+)(?:-(\d+))?`?"
)

MERMAID_BLOCK_PATTERN = re.compile(r"```mermaid\b.*?```", re.DOTALL)


def split_sections(md: str) -> dict[str, str]:
    """按一级标题（## ）切分小节，返回 {标题: 内容}"""
    sections: dict[str, str] = {}
    current_title = "_前言_"
    current_body: list[str] = []
    for line in md.splitlines():
        if line.startswith("## "):
            sections[current_title] = "\n".join(current_body)
            current_title = line[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    sections[current_title] = "\n".join(current_body)
    return sections


def count_chinese_chars(s: str) -> int:
    """统计中文字符数（粗略估计字数）"""
    return sum(1 for ch in s if "一" <= ch <= "鿿")


def grep_file_line(path: str, line: int) -> bool:
    """验证某个 file:line 在仓库中真实存在"""
    full = REPO_ROOT / path
    if not full.exists():
        return False
    try:
        with open(full, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return 0 < line <= len(lines)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 各检查项
# ---------------------------------------------------------------------------

def check_filename(report: Report, md_path: Path):
    name = md_path.name
    ok = bool(re.match(r"^[0-9]+(\.[0-9A-Z]+)*_[^\s]+\.md$", name))
    report.add(
        "文件命名（<编号>_<标题>.md，无空格）",
        ok,
        "FAIL",
        f"实际: {name}" if not ok else "",
    )


def check_frontmatter(report: Report, md: str) -> dict:
    """检查 YAML frontmatter 并返回解析后的字典"""
    m = re.match(r"^---\n(.*?)\n---\n", md, re.DOTALL)
    if not m:
        report.add("YAML frontmatter 存在", False, "FAIL",
                   "文件开头必须有 --- 包裹的 YAML 块")
        return {}
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        report.add("YAML frontmatter 解析", False, "FAIL", str(e))
        return {}

    required = ["section_id", "title", "priority", "last_verified"]
    missing = [k for k in required if k not in data]
    report.add(
        "YAML frontmatter 必填字段",
        not missing,
        "FAIL",
        f"缺字段: {missing}" if missing else "",
    )
    return data


def check_section_titles(report: Report, md: str):
    missing = []
    last_pos = -1
    order_ok = True
    for label, pattern in SECTION_TITLES:
        m = re.search(pattern, md, re.MULTILINE)
        if not m:
            missing.append(label)
        else:
            if m.start() <= last_pos:
                order_ok = False
            last_pos = m.start()
    report.add(
        "十二段标题齐全",
        not missing,
        "FAIL",
        f"缺失: {missing}" if missing else "",
    )
    report.add(
        "十二段标题顺序正确",
        order_ok,
        "FAIL",
        "标题出现顺序与规范不符" if not order_ok else "",
    )


def check_file_line_refs(report: Report, md: str, materials: dict):
    """检查所有 file:line 引用"""
    refs = FILE_LINE_PATTERN.findall(md)
    if not refs:
        report.add(
            "file:line 引用数量（≥ 6）",
            False,
            "FAIL",
            "未找到任何 file:line 引用",
        )
        return

    allowed = {}
    if materials:
        for entry in materials.get("allowed_refs", []) or []:
            allowed[entry["path"]] = set(entry.get("lines", []))

    invalid_grep = []
    not_in_allowed = []

    for path, start, end in refs:
        line_start = int(start)
        line_end = int(end) if end else line_start

        # 实际 grep 验证
        for ln in range(line_start, line_end + 1):
            if not grep_file_line(path, ln):
                invalid_grep.append(f"{path}:{ln}")

        # 物料包白名单验证（如有提供）
        if materials:
            if path not in allowed:
                not_in_allowed.append(f"{path}（整个文件未在 allowed_refs）")
            else:
                for ln in range(line_start, line_end + 1):
                    if ln not in allowed[path]:
                        not_in_allowed.append(f"{path}:{ln}")

    report.add(
        f"file:line 引用数量（实际 {len(refs)} 条，要求 ≥ 6）",
        len(refs) >= 6,
        "FAIL",
        "",
    )
    report.add(
        "file:line 全部可 Grep 命中",
        not invalid_grep,
        "FAIL",
        f"无效引用 {len(invalid_grep)} 条:\n  " + "\n  ".join(invalid_grep[:10])
        if invalid_grep else "",
    )
    if materials:
        report.add(
            "file:line 全部在物料包 allowed_refs 中",
            not not_in_allowed,
            "FAIL",
            f"越界引用 {len(not_in_allowed)} 条:\n  " + "\n  ".join(not_in_allowed[:10])
            if not_in_allowed else "",
        )


def check_mermaid_blocks(report: Report, md: str):
    blocks = MERMAID_BLOCK_PATTERN.findall(md)
    report.add(
        f"Mermaid 块数量（实际 {len(blocks)}，要求 ≥ 2）",
        len(blocks) >= 2,
        "FAIL",
        "",
    )

    # 可选：用 mmdc 校验语法
    try:
        subprocess.run(["mmdc", "--version"], capture_output=True, check=True)
        mmdc_available = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        mmdc_available = False

    if mmdc_available:
        # 简单校验前两个 Mermaid 块（限制时间）
        for i, block in enumerate(blocks[:2]):
            content = block[len("```mermaid"):-3].strip()
            tmp = REPO_ROOT / f".tmp_mermaid_{i}.mmd"
            tmp.write_text(content, encoding="utf-8")
            try:
                result = subprocess.run(
                    ["mmdc", "-i", str(tmp), "-o", f"{tmp}.svg", "--quiet"],
                    capture_output=True,
                    timeout=15,
                )
                report.add(
                    f"Mermaid 块 #{i + 1} 语法",
                    result.returncode == 0,
                    "WARN",
                    result.stderr.decode("utf-8", errors="ignore")[:200]
                    if result.returncode != 0 else "",
                )
            except subprocess.TimeoutExpired:
                report.add(f"Mermaid 块 #{i + 1} 语法", False, "WARN", "mmdc 超时")
            finally:
                tmp.unlink(missing_ok=True)
                Path(f"{tmp}.svg").unlink(missing_ok=True)
    else:
        report.add(
            "Mermaid 语法校验（mmdc 可选）",
            True,
            "WARN",
            "未安装 mmdc，跳过语法校验（npm i -g @mermaid-js/mermaid-cli 可启用）",
        )


def check_section_lengths(report: Report, sections: dict[str, str], materials: dict):
    outline = (materials or {}).get("section_outline", {}) or {}
    # 默认字数下限（无物料包时）
    default_mins = {
        "学习目标": 50,
        "前置知识": 50,
        "场景故事": 200,
        "协议正文": 600,
        "源码导读": 200,
        "简化代码片段": 100,
        "实测数据": 100,
        "FAQ": 200,
    }

    short_sections = []
    for title, body in sections.items():
        words = count_chinese_chars(body)
        for key, min_w in default_mins.items():
            if key in title and words < min_w:
                short_sections.append(f"{title}: {words}/{min_w} 字")
                break

    report.add(
        "各段字数下限",
        not short_sections,
        "FAIL",
        "字数不足:\n  " + "\n  ".join(short_sections) if short_sections else "",
    )


def check_call_chain_layers(report: Report, sections: dict[str, str]):
    body = next((v for k, v in sections.items() if "分层调用链" in k), "")
    # 计算分层标记数（粗略：每行含 "→" 或行号引用）
    layer_lines = [
        ln for ln in body.splitlines()
        if FILE_LINE_PATTERN.search(ln) or "→" in ln or "->" in ln
    ]
    report.add(
        f"分层调用链层数（实际 {len(layer_lines)}，要求 ≥ 4）",
        len(layer_lines) >= 4,
        "FAIL",
        "",
    )


def check_faq_homework_quiz(report: Report, sections: dict[str, str]):
    """检查 FAQ、自测题、上路任务数量"""
    body = ""
    for k, v in sections.items():
        if any(w in k for w in ["FAQ", "自测题", "上路任务"]):
            body += "\n" + v

    # FAQ 计数：找 "Q1" / "**Q" / "### Q" 等模式
    faq_count = len(re.findall(r"(?:^|\n)\s*(?:###\s+)?(?:\*\*)?Q\d+", body))
    homework_count = body.count("上路任务") + len(
        re.findall(r"(?:^|\n)\s*\d+\.\s+.+(?:任务|完成|实现|跑通)", body)
    )
    quiz_count = len(re.findall(r"(?:^|\n)\s*(?:###\s+)?自测题\s*\d+", body))
    # 备选：直接数 §12 中编号列表项
    list_items = len(re.findall(r"(?:^|\n)\s*\d+\.\s", body))

    report.add(
        f"FAQ 数量（实际 {faq_count}，要求 ≥ 3）",
        faq_count >= 3,
        "FAIL",
        "",
    )
    report.add(
        f"上路任务数量（实际 {homework_count}，要求 ≥ 2；总编号列表项 {list_items}）",
        homework_count >= 2 or list_items >= 5,
        "FAIL",
        "",
    )
    report.add(
        f"自测题数量（实际 {quiz_count}，要求 ≥ 3）",
        quiz_count >= 3,
        "WARN",
        "若已放在附录 D，请确保附录有对应文件",
    )


def check_terms(report: Report, md: str, materials: dict):
    if not materials:
        report.add("术语黑名单（需物料包）", True, "WARN", "未提供物料包，跳过")
        return
    forbidden_hits = []
    for term in (materials.get("terms") or []):
        for bad in term.get("forbidden", []) or []:
            if bad in md:
                forbidden_hits.append(f"{bad} → 应使用 {term.get('canonical')}")
    report.add(
        "术语黑名单",
        not forbidden_hits,
        "FAIL",
        "\n".join(forbidden_hits) if forbidden_hits else "",
    )


def check_measured_data(report: Report, sections: dict[str, str]):
    body = next((v for k, v in sections.items() if "实测数据" in k), "")
    keywords = ["时延", "成功率", "重试"]
    missing = [k for k in keywords if k not in body]
    report.add(
        "实测数据关键字（时延/成功率/重试）",
        not missing,
        "WARN",
        f"缺关键字: {missing}" if missing else "",
    )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="v2 章节自检脚本")
    parser.add_argument("md_file", help="章节 markdown 文件路径")
    parser.add_argument(
        "--materials", "-m",
        help="物料包 YAML 路径（不提供则跳过白名单/术语检查）",
    )
    args = parser.parse_args()

    md_path = Path(args.md_file)
    if not md_path.exists():
        print(f"ERROR: 文件不存在 {md_path}", file=sys.stderr)
        sys.exit(2)

    md = md_path.read_text(encoding="utf-8")

    materials = {}
    if args.materials:
        mat_path = Path(args.materials)
        if not mat_path.exists():
            print(f"WARN: 物料包不存在 {mat_path}，跳过白名单检查", file=sys.stderr)
        else:
            try:
                materials = yaml.safe_load(mat_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as e:
                print(f"WARN: 物料包解析失败 {e}", file=sys.stderr)

    report = Report(file=str(md_path))

    # 顺序执行检查
    check_filename(report, md_path)
    check_frontmatter(report, md)
    check_section_titles(report, md)

    sections = split_sections(md)
    check_file_line_refs(report, md, materials)
    check_mermaid_blocks(report, md)
    check_section_lengths(report, sections, materials)
    check_call_chain_layers(report, sections)
    check_faq_homework_quiz(report, sections)
    check_terms(report, md, materials)
    check_measured_data(report, sections)

    report.print_summary()

    if report.has_fail:
        sys.exit(1)
    elif report.has_warn:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
