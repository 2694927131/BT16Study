#!/usr/bin/env python3
"""v2 进度速查脚本 —— scripts/progress.py

用法:
    python scripts/progress.py

作用:
    一键扫描 v2 当前进度,不依赖任何状态记录(直接读文件系统真相),输出:
    - 物料包就绪数 / 章节文件数 / verify PASS 数
    - 每节当前状态(物料包/脚手架/内容/自检 四阶段)
    - 待办优先级提示
    - 最近 5 条 git 提交

适用场景:
    - 你(或新模型)接手时第一时间运行此脚本
    - 用 `git log --oneline -10` 兜底交叉验证
    - 不写入任何状态,只读输出
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认 GBK,章节/物料包路径含中文会触发 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
MATERIALS_ROOT = REPO_ROOT / "doc" / "学习资料_v2" / "_物料包"
V2_ROOT = REPO_ROOT / "doc" / "学习资料_v2"

# 与 doc/开发计划.md / 升级改造方案_v2.md 一致
PRIORITY_GROUPS = [
    ("M6 P0", ["12", "16"], "LE Audio 全景 + 音频路由 / Audio HAL"),
    ("M6 P1", ["13", "14"], "安全与加密(13.1/13.3/13.4/13.5) + OBEX"),
    ("M7 P0", ["17", "18"], "多设备共存 + BluetoothManagerService Kotlin"),
    ("M7 P1", ["19"], "性能 BQR"),
    ("扩展",   ["15", "20", "21", "22", "23", "24"], "HID/PAN + 测试 + aconfig + Socket + Vendor + 测距"),
    ("v1 回填", ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11"], "v1 章节升级 v2"),
]


def scan_materials() -> dict[str, dict]:
    """扫描物料包目录,返回 {section_id: {chapter: str, yaml_path: Path, ...}}"""
    result: dict[str, dict] = {}
    if not MATERIALS_ROOT.exists():
        return result

    for chapter_dir in sorted(MATERIALS_ROOT.iterdir()):
        if not chapter_dir.is_dir() or chapter_dir.name.startswith("_"):
            continue
        chapter_num = chapter_dir.name.split("_")[0]
        for yaml_file in sorted(chapter_dir.glob("*.yaml")):
            # 文件名形如 "13.2_SMP详解.yaml"
            m = re.match(r"^([\d]+\.[\d]+)_", yaml_file.name)
            if not m:
                continue
            sid = m.group(1)
            result[sid] = {
                "chapter": chapter_num,
                "yaml_path": yaml_file,
                "yaml_rel": yaml_file.relative_to(REPO_ROOT),
            }
    return result


def find_section_md(sid: str, chapter_num: str) -> Path | None:
    """在 doc/学习资料_v2/<章>/ 下找以 sid 开头的 md 文件"""
    chapter_dirs = list(V2_ROOT.glob(f"{chapter_num}_*"))
    for cd in chapter_dirs:
        for md in cd.glob(f"{sid}_*.md"):
            return md
    return None


def md_status(md_path: Path) -> str:
    """根据章节 md 文件内容判断状态"""
    if not md_path or not md_path.exists():
        return "⬜ 未生成"
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    # 仅脚手架: 大量 <!-- 提示/约束 --> 但无中文段落
    todo_markers = text.count("<!-- ↑ 在此段下方填写中文内容 -->")
    if todo_markers >= 8:
        # 仍是空脚手架(11 段空标记应该都在,允许少量段已填)
        chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
        if chinese_chars < 500:
            return "🟡 脚手架已生成,内容未填"
        else:
            return "🟡 内容部分填充"
    return "✅ 内容已填(待自检确认)"


def git_recent_commits(n: int = 5) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "log", "--oneline", f"-{n}"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        return out.stdout.splitlines()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def tracking_record_next_step() -> str:
    """从 doc/开发跟踪记录.md 抽取「下一步」段落"""
    track = REPO_ROOT / "doc" / "开发跟踪记录.md"
    if not track.exists():
        return "(未找到开发跟踪记录.md)"
    text = track.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"##\s*\d+\.\s*下一步\s*\n+(.+?)(?:\n##\s|\Z)", text, re.DOTALL)
    if not m:
        return "(未找到「下一步」段)"
    body = m.group(1).strip()
    lines = [ln for ln in body.splitlines() if ln.strip()]
    return "\n".join(lines[:12])  # 取前 12 行


def main():
    print("=" * 70)
    print("v2 进度速查（直接读文件系统,不依赖任何状态文件）")
    print("=" * 70)

    materials = scan_materials()
    total_materials = len(materials)

    print(f"\n[统计] 物料包就绪: {total_materials} 个")

    # 按章分组统计
    by_chapter: dict[str, list] = {}
    for sid, info in materials.items():
        ch = info["chapter"]
        by_chapter.setdefault(ch, []).append(sid)

    print(f"        覆盖章: {sorted(by_chapter.keys())}")

    # 详细清单
    print("\n[详细清单（按节编号排序）]")
    if not materials:
        print("  (无物料包)")
    for sid in sorted(materials.keys(), key=lambda x: tuple(int(n) for n in x.split("."))):
        info = materials[sid]
        md_path = find_section_md(sid, info["chapter"])
        status = md_status(md_path) if md_path else "⬜ 章节文件未生成"
        md_rel = md_path.relative_to(REPO_ROOT) if md_path else "-"
        print(f"  [{sid}] {status}")
        print(f"        物料包: {info['yaml_rel']}")
        print(f"        章节md: {md_rel}")

    # 待办按优先级
    print("\n[待办优先级（物料包尚未制作的章）]")
    for tag, chapters, desc in PRIORITY_GROUPS:
        done = sum(1 for ch in chapters if ch in by_chapter)
        missing = [ch for ch in chapters if ch not in by_chapter]
        marker = "✅" if not missing else f"⬜ 缺 ch{','.join(missing)}"
        print(f"  {tag:8} ({desc})")
        print(f"           章节就绪 {done}/{len(chapters)}  {marker}")

    # 跟踪记录的「下一步」
    print("\n[跟踪记录中的「下一步」]")
    print(tracking_record_next_step())

    # 最近 git 提交
    print("\n[最近 5 条 git 提交]")
    for line in git_recent_commits(5):
        print(f"  {line}")

    # 行动建议
    print("\n" + "=" * 70)
    print("行动建议")
    print("=" * 70)
    if total_materials == 0:
        print("  → 物料包为空,需要强模型/人工先制作物料包")
    else:
        # 找第一个未完成的
        next_todo = None
        for sid in sorted(materials.keys(), key=lambda x: tuple(int(n) for n in x.split("."))):
            md = find_section_md(sid, materials[sid]["chapter"])
            if not md or md_status(md).startswith("🟡") or md_status(md).startswith("⬜"):
                next_todo = sid
                break
        if next_todo:
            yaml_rel = materials[next_todo]["yaml_rel"]
            print(f"  → 下一节建议: {next_todo}")
            print(f"     1) 读物料包: {yaml_rel}")
            print(f"     2) 若脚手架未生成,跑: python scripts/scaffold_section.py {yaml_rel}")
            print(f"     3) 在脚手架填空")
            print(f"     4) 自检: python scripts/verify_section.py <章节md> --materials {yaml_rel}")
        else:
            print("  → 所有已制作物料包对应章节均已填空。可:")
            print("     A) 让强模型继续制作下批物料包(M6 P0 优先)")
            print("     B) 对已完成章节运行 verify_section.py 抽审")

    print()


if __name__ == "__main__":
    main()
