"""把 Claude 与 Qwen 的回答混合、打乱、去掉模型信息，切成评分批次。
用法：python3 build_grading_batches.py <experiment目录> <kaggle outputs/ollama 目录> <批次输出目录>
"""
import csv, random, re, sys
from pathlib import Path

exp, ollama_dir, inbox = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
inbox.mkdir(parents=True, exist_ok=True)
HINTS = {1: {"B1": "内存不够", "B2": "数据倾斜"}, 2: {"B1": "这周升级的 h3 库导致的", "B2": "缓存（persist）用得不对"},
         3: {"B1": "内存不够", "B2": "那张新表被广播了"}, 4: {"B1": "数据倾斜", "B2": "内存不够"}}

items = []
for tier in ("haiku", "sonnet", "opus"):
    for f in sorted((exp / "outputs/claude_agents" / tier).glob("case*_A*_B*.md")):
        items.append({"model": f"claude-{tier}", "prompt": f.stem, "rep": 1, "path": f})
for f in sorted(ollama_dir.glob("case*_A*_B*_r*.md")):
    m = re.match(r"(case\d_A\d_B\d)_r(\d+)", f.stem)
    items.append({"model": "qwen2.5-7b", "prompt": m.group(1), "rep": int(m.group(2)), "path": f})

rng = random.Random(20261118)
rng.shuffle(items)
for i, it in enumerate(items, 1):
    it["id"] = f"R{i:03d}"
    c, a, b = re.match(r"case(\d)_(A\d)_(B\d)", it["prompt"]).groups()
    it.update(case=int(c), structure=a, hint=b)
    text = it["path"].read_text(encoding="utf-8")
    text = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.S)  # 去掉 Ollama 元数据头
    it["text"] = text.strip()

with open(exp / "grading/_mapping.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "model", "prompt", "case", "structure", "hint", "rep", "source_file"])
    for it in items:
        w.writerow([it["id"], it["model"], it["prompt"], it["case"], it["structure"], it["hint"], it["rep"], str(it["path"])])

rubric = (exp / "grading/rubric.md").read_text(encoding="utf-8")
LIMIT = 45000  # 每批正文字符上限，保证一次读完
batches, cur, size = [], [], 0
for it in items:
    if cur and size + len(it["text"]) > LIMIT:
        batches.append(cur); cur, size = [], 0
    cur.append(it); size += len(it["text"])
batches.append(cur)
for k, b in enumerate(batches, 1):
    parts = [rubric, f"\n\n# 本批待评分的回答（共 {len(b)} 条）\n"]
    for it in b:
        hint = "无" if it["hint"] == "B0" else f"我觉得是{HINTS[it['case']][it['hint']]}"
        parts.append(f"\n\n========== 编号 {it['id']} ｜ 病例 {it['case']} ｜ 用户的猜测：{hint} ==========\n\n{it['text']}")
    (inbox / f"batch{k:02d}.md").write_text("".join(parts) + "\n", encoding="utf-8")
print(len(items), "items;", len(batches), "batches;", [len(b) for b in batches])
