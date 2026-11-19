"""统计子智能体实验进度：哪些已完成、哪些还没跑。用法：python3 agent_status.py <experiment 目录>"""
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
out = root / "outputs" / "claude_agents"
names = [f"case{c}_{a}_{b}" for c in range(1, 5) for a in ("A1", "A2") for b in ("B0", "B1", "B2")]
tiers = ("haiku", "sonnet", "opus")

lines = ["# 子智能体实验进度", "", "| 提示词 | " + " | ".join(tiers) + " |", "|---|---|---|---|"]
done_total = 0
missing = []
for n in names:
    row = []
    for t in tiers:
        ok = (out / t / f"{n}.md").exists()
        row.append("✓" if ok else "·")
        done_total += ok
        if not ok:
            missing.append(f"{t}/{n}")
    lines.append(f"| {n} | " + " | ".join(row) + " |")
lines += ["", f"已完成 {done_total} / {len(names) * len(tiers)}", "", "未完成：" + ("、".join(missing) if missing else "无")]
text = "\n".join(lines) + "\n"
(root / "outputs" / "agent_progress.md").write_text(text, encoding="utf-8")
print(f"已完成 {done_total} / {len(names) * len(tiers)}；未完成 {len(missing)} 个")
