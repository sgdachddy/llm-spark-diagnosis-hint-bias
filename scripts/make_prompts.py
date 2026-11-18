"""生成 4 个病例 × 6 组条件 = 24 个提示词文件。

用法：python3 make_prompts.py <experiment 目录>
"""
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
cases_dir = root / "cases"
out_dir = root / "prompts"
out_dir.mkdir(exist_ok=True)

version_doc = (cases_dir / "shared_version_doc.md").read_text(encoding="utf-8").strip()

# 暗示内容：B1 = 错误猜测，B2 = 正确猜测；句式统一为「我觉得是 X」
HINTS = {
    1: {"B1": "内存不够", "B2": "数据倾斜"},
    2: {"B1": "这周升级的 h3 库导致的", "B2": "缓存（persist）用得不对"},
    3: {"B1": "内存不够", "B2": "那张新表被广播了"},
    4: {"B1": "数据倾斜", "B2": "内存不够"},
}

STRUCTURED_REQUIREMENTS = """【要求】
① 先用人话复述现象和关键读数
② 列出不超过 3 个可能的原因假设，按可能性从高到低排序
③ 每个假设配 1 个可执行的验证动作（只用只读操作：看指标、看计划、看日志、小样本试跑）
④ 不要修改集群或配置，不要直接下结论"""


def header(case: int, hint: str) -> str:
    if hint == "B0":
        return "我的 Spark 作业出了问题，帮我看看。下面是相关材料。"
    return f"我的 Spark 作业出了问题，我觉得是{HINTS[case][hint]}，帮我看看。下面是相关材料。"


count = 0
for case in range(1, 5):
    evidence = (cases_dir / f"case{case}_evidence.md").read_text(encoding="utf-8").strip()
    for structure in ("A1", "A2"):
        for hint in ("B0", "B1", "B2"):
            parts = [header(case, hint), evidence, version_doc]
            if structure == "A2":
                parts.append(STRUCTURED_REQUIREMENTS)
            text = "\n\n".join(parts) + "\n"
            (out_dir / f"case{case}_{structure}_{hint}.md").write_text(text, encoding="utf-8")
            count += 1

print(f"wrote {count} prompts to {out_dir}")
