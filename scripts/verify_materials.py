#!/usr/bin/env python3
"""物料包自检脚本 —— scripts/verify_materials.py

用法:
    python scripts/verify_materials.py <物料包 yaml 文件 或 目录>

检查项:
    1. YAML 语法合法
    2. 必填字段齐全（meta / allowed_refs / section_outline）
    3. allowed_refs 中每条 file:line 都能在仓库中实际找到
    4. code_snippets 中每个 source 对应的 file:line 真实存在
    5. mermaid_templates 中编号必须在 doc/v2_Mermaid模板库.md 中存在
    6. terms 字段格式正确（含 canonical / forbidden）
    7. section_outline 含十二段配置

返回值:
    0 = PASS
    1 = FAIL
    2 = WARN-only

作用：物料包是 v2 章节的"地基"，物料包错则整章全错。本脚本由强模型/人工
     在物料包制作完毕后立即运行，确保不把伪造的引用流到中等模型。
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

REQUIRED_META_FIELDS = ["section_id", "title", "priority", "last_verified"]
REQUIRED_OUTLINE_KEYS = [
    "s02_objectives", "s03_prereq", "s04_scene", "s05_protocol",
    "s06_call_chain", "s07_source_guide", "s08_simplified_code",
    "s09_mermaid", "s10_measured", "s11_debug", "s12_faq_homework",
]

# 模板库中已定义的编号
KNOWN_TEMPLATES = {
    "T-SEQ-3", "T-SEQ-5", "T-SEQ-PEER", "T-SEQ-PAIR",
    "T-STATE-2", "T-STATE-3", "T-STATE-NESTED",
    "T-ARCH-4", "T-ARCH-6", "T-ARCH-MODULE",
    "T-FLOW-3", "T-FLOW-DECISION", "T-FLOW-PIPELINE",
    "T-CALL-CHAIN", "T-PCAP", "T-CLASS",
}


class Report:
    def __init__(self, file: str):
        self.file = file
        self.fails: list[str] = []
        self.warns: list[str] = []
        self.passes: list[str] = []

    def fail(self, msg: str):
        self.fails.append(msg)

    def warn(self, msg: str):
        self.warns.append(msg)

    def ok(self, msg: str):
        self.passes.append(msg)

    def print(self) -> int:
        print(f"\n=== {self.file} ===")
        for p in self.passes:
            print(f"  [OK]   {p}")
        for w in self.warns:
            print(f"  [WARN] {w}")
        for f in self.fails:
            print(f"  [FAIL] {f}")
        if self.fails:
            print(f"  Result: FAIL ({len(self.fails)} errors)")
            return 1
        elif self.warns:
            print(f"  Result: WARN ({len(self.warns)} warnings)")
            return 2
        else:
            print("  Result: PASS")
            return 0


def grep_line_exists(path: str, line: int) -> bool:
    """验证某个 file:line 在仓库中真实存在"""
    full = REPO_ROOT / path
    if not full.exists():
        return False
    try:
        with open(full, encoding="utf-8", errors="ignore") as f:
            total = sum(1 for _ in f)
        return 0 < line <= total
    except OSError:
        return False


def parse_source_ref(src: str) -> tuple[str, int, int] | None:
    """解析 'system/xxx/yyy.cc:83-115' 或 'system/xxx/yyy.cc:83'"""
    m = re.match(r"^([a-zA-Z0-9_./\-]+):(\d+)(?:-(\d+))?$", src.strip())
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))


def check_yaml_schema(data: dict, report: Report):
    """检查必填字段"""
    if "meta" not in data:
        report.fail("缺 meta 字段")
        return
    meta = data["meta"]
    missing = [k for k in REQUIRED_META_FIELDS if k not in meta]
    if missing:
        report.fail(f"meta 缺字段: {missing}")
    else:
        report.ok(f"meta 必填字段齐全（{REQUIRED_META_FIELDS}）")

    if "allowed_refs" not in data or not data["allowed_refs"]:
        report.fail("allowed_refs 为空 —— 物料包必须提供引用清单")
    if "section_outline" not in data:
        report.fail("缺 section_outline 字段")
    else:
        outline = data["section_outline"] or {}
        missing_keys = [k for k in REQUIRED_OUTLINE_KEYS if k not in outline]
        if missing_keys:
            report.fail(f"section_outline 缺段配置: {missing_keys}")
        else:
            report.ok(f"section_outline 含全部 {len(REQUIRED_OUTLINE_KEYS)} 段配置")


def check_allowed_refs(data: dict, report: Report):
    """逐条 grep 验证 allowed_refs"""
    refs = data.get("allowed_refs") or []
    invalid = []
    total_lines = 0
    for entry in refs:
        path = entry.get("path", "")
        lines = entry.get("lines") or []
        if not path:
            invalid.append("条目缺 path 字段")
            continue
        # 检查 path 文件是否存在
        if not (REPO_ROOT / path).exists():
            invalid.append(f"{path}（文件不存在）")
            continue
        # 检查每个行号
        for ln in lines:
            total_lines += 1
            if not grep_line_exists(path, ln):
                invalid.append(f"{path}:{ln}（行号超出文件范围）")

    if invalid:
        report.fail(
            f"allowed_refs 有 {len(invalid)} 条无效引用:\n      "
            + "\n      ".join(invalid[:15])
        )
    else:
        report.ok(f"allowed_refs 共 {len(refs)} 个文件 / {total_lines} 个行号引用，全部验证通过")


def check_code_snippets(data: dict, report: Report):
    """检查 code_snippets 中 source 真实性"""
    snippets = data.get("code_snippets") or []
    if not snippets:
        report.warn("code_snippets 为空，建议至少预喂 2 段关键代码")
        return

    invalid = []
    ids_seen = set()
    for snip in snippets:
        sid = snip.get("id", "")
        if not sid:
            invalid.append("片段缺 id")
            continue
        if sid in ids_seen:
            invalid.append(f"id 重复: {sid}")
        ids_seen.add(sid)

        source = snip.get("source", "")
        parsed = parse_source_ref(source)
        if not parsed:
            invalid.append(f"{sid}: source 格式错（应为 'path:start-end'）")
            continue
        path, start, end = parsed
        if not (REPO_ROOT / path).exists():
            invalid.append(f"{sid}: 文件不存在 {path}")
            continue
        if not grep_line_exists(path, start) or not grep_line_exists(path, end):
            invalid.append(f"{sid}: 行号范围超界 {source}")

        if "code" not in snip:
            invalid.append(f"{sid}: 缺 code 字段（必须预截取代码）")

    if invalid:
        report.fail(
            f"code_snippets 有 {len(invalid)} 个问题:\n      "
            + "\n      ".join(invalid)
        )
    else:
        report.ok(f"code_snippets 共 {len(snippets)} 段，全部验证通过")


def check_mermaid_templates(data: dict, report: Report):
    """检查 mermaid_templates 编号合法"""
    templates = data.get("mermaid_templates") or []
    if not templates:
        report.warn("mermaid_templates 为空，建议至少推荐 2 个模板")
        return
    invalid = []
    for t in templates:
        tid = t.get("id", "")
        if tid not in KNOWN_TEMPLATES:
            invalid.append(f"未知模板编号: {tid}（请在 doc/v2_Mermaid模板库.md 中确认或追加）")
    if invalid:
        report.fail("\n      ".join(invalid))
    else:
        report.ok(f"mermaid_templates 共 {len(templates)} 个，编号全部合法")


def check_terms(data: dict, report: Report):
    """检查术语字段格式"""
    terms = data.get("terms") or []
    if not terms:
        report.warn("terms 为空，建议至少提供本节涉及的 3-5 个术语约束")
        return
    invalid = []
    for term in terms:
        if "canonical" not in term:
            invalid.append("术语条目缺 canonical")
        if "forbidden" in term and not isinstance(term["forbidden"], list):
            invalid.append(f"{term.get('canonical')}: forbidden 必须是列表")
    if invalid:
        report.fail("\n      ".join(invalid))
    else:
        report.ok(f"terms 共 {len(terms)} 条，格式合法")


def verify_one(path: Path) -> int:
    """验证单个物料包文件"""
    report = Report(str(path))

    if not path.exists():
        report.fail("文件不存在")
        return report.print()

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        report.fail(f"YAML 解析失败: {e}")
        return report.print()

    if not isinstance(data, dict):
        report.fail("根节点必须是字典")
        return report.print()

    check_yaml_schema(data, report)
    check_allowed_refs(data, report)
    check_code_snippets(data, report)
    check_mermaid_templates(data, report)
    check_terms(data, report)

    return report.print()


def main():
    parser = argparse.ArgumentParser(description="v2 物料包自检脚本")
    parser.add_argument("target", help="物料包 yaml 文件或包含物料包的目录")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"ERROR: 目标不存在 {target}", file=sys.stderr)
        sys.exit(2)

    if target.is_file():
        sys.exit(verify_one(target))

    # 目录批量验证
    yamls = sorted(target.rglob("*.yaml"))
    if not yamls:
        print(f"ERROR: 目录 {target} 下未找到 .yaml 文件", file=sys.stderr)
        sys.exit(2)

    print(f"批量验证 {len(yamls)} 个物料包...")
    exit_codes = []
    for y in yamls:
        exit_codes.append(verify_one(y))

    print("\n" + "=" * 60)
    fails = sum(1 for c in exit_codes if c == 1)
    warns = sum(1 for c in exit_codes if c == 2)
    passes = sum(1 for c in exit_codes if c == 0)
    print(f"总结: PASS={passes} / WARN={warns} / FAIL={fails}")
    sys.exit(1 if fails else (2 if warns else 0))


if __name__ == "__main__":
    main()
