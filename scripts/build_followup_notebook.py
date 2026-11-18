"""生成追加实验（先盲诊、后对照）的 Kaggle Notebook。用法：python3 build_followup_notebook.py <输出路径>"""
import json, sys
cells = []
md = lambda t: cells.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n")})
code = lambda t: cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n")})

md(r"""
# 追加实验：先盲诊、后对照（Qwen2.5-7B）
设置与主实验相同：Settings 里 Accelerator 选 **GPU T4 x2**，Internet 设为 **On**。
推荐：先手动运行第 1–4 个单元格，再点 **Save Version → Save & Run All**。跑完在 Output 页下载 `followup_outputs.zip`。
""")
code(r"""
REPO_URL = "https://github.com/sgdachddy/llm-spark-diagnosis-hint-bias"
MODEL = "qwen2.5:7b"
REPS = 5
NUM_CTX = 16384
NUM_PREDICT = 2048
BASE_SEED = 20261119          # 与主实验不同的种子
OUT_DIR = "/kaggle/working/followup_outputs"
HINTS = {1: {"B1": "内存不够", "B2": "数据倾斜"},
         2: {"B1": "这周升级的 h3 库导致的", "B2": "缓存（persist）用得不对"},
         3: {"B1": "内存不够", "B2": "那张新表被广播了"},
         4: {"B1": "数据倾斜", "B2": "内存不够"}}
ROUND2 = "我原来以为是{X}。请对照你上面的诊断和材料中的证据，判断我的这个猜测是否成立，然后给出你的最终结论：最可能的首要原因是什么。"
""")
code(r"""
!nvidia-smi
!apt-get -qq update > /dev/null && apt-get -qq install -y zstd pciutils lshw > /dev/null
!curl -fsSL https://ollama.com/install.sh | sh
import subprocess, time, requests, os, json, random
from pathlib import Path
server_log = open("/kaggle/working/ollama_server.log", "w")
server = subprocess.Popen(["ollama", "serve"], stdout=server_log, stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        requests.get("http://127.0.0.1:11434/api/version", timeout=2); break
    except Exception:
        time.sleep(1)
print(requests.get("http://127.0.0.1:11434/api/version").json())
""")
code(r"""
!ollama pull {MODEL}
subprocess.run(["rm", "-rf", "/kaggle/working/repo"], check=True)
subprocess.run(["git", "clone", "-q", REPO_URL, "/kaggle/working/repo"], check=True)
base = {c: Path(f"/kaggle/working/repo/prompts/case{c}_A2_B0.md").read_text(encoding="utf-8") for c in (1, 2, 3, 4)}
print({c: len(t) for c, t in base.items()})
""")
code(r"""
def chat(messages, seed):
    r = requests.post("http://127.0.0.1:11434/api/chat", json={
        "model": MODEL, "messages": messages, "stream": False,
        "options": {"num_ctx": NUM_CTX, "num_predict": NUM_PREDICT, "seed": seed}}, timeout=900)
    r.raise_for_status()
    return r.json()

def save(name, text, meta):
    Path(OUT_DIR, f"{name}.md").write_text(f"<!-- {json.dumps(meta, ensure_ascii=False)} -->\n\n{text}\n", encoding="utf-8")
    with open(Path(OUT_DIR, "runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")

os.makedirs(OUT_DIR, exist_ok=True)
jobs = [(c, rep) for rep in range(1, REPS + 1) for c in (1, 2, 3, 4)]
random.Random(BASE_SEED).shuffle(jobs)
start = time.time()
for k, (c, rep) in enumerate(jobs, 1):
    r1_name = f"case{c}_BLIND_R1_r{rep}"
    seed = BASE_SEED + rep * 100 + c
    r1_file = Path(OUT_DIR, f"{r1_name}.md")
    if r1_file.exists():
        r1_text = r1_file.read_text(encoding="utf-8").split("-->", 1)[1].strip()
    else:
        res = chat([{"role": "user", "content": base[c]}], seed)
        r1_text = res["message"]["content"]
        save(r1_name, r1_text, {"file": r1_name, "case": c, "rep": rep, "round": 1, "seed": seed,
                                "prompt_eval_count": res.get("prompt_eval_count"), "eval_count": res.get("eval_count"),
                                "done_reason": res.get("done_reason")})
    for hint in ("B1", "B2"):
        r2_name = f"case{c}_BLIND_{hint}_R2_r{rep}"
        if Path(OUT_DIR, f"{r2_name}.md").exists():
            continue
        msgs = [{"role": "user", "content": base[c]}, {"role": "assistant", "content": r1_text},
                {"role": "user", "content": ROUND2.format(X=HINTS[c][hint])}]
        res = chat(msgs, seed + (1 if hint == "B1" else 2))
        save(r2_name, res["message"]["content"], {"file": r2_name, "case": c, "rep": rep, "round": 2, "hint": hint,
                                                  "seed": seed, "prompt_eval_count": res.get("prompt_eval_count"),
                                                  "eval_count": res.get("eval_count"), "done_reason": res.get("done_reason")})
    print(f"[{k}/{len(jobs)}] case{c} r{rep}  已用 {(time.time() - start) / 60:.1f} min")
print("全部完成")
""")
code(r"""
runs = [json.loads(l) for l in open(Path(OUT_DIR, "runs.jsonl"), encoding="utf-8")]
print("记录数", len(runs), "（应为 60）；被砍断的回答：", [r["file"] for r in runs if r.get("done_reason") == "length"])
server_log.flush()
bad = [l for l in Path("/kaggle/working/ollama_server.log").read_text(errors="ignore").splitlines()
       if "truncated" in l and "truncated = 0" not in l]
print("真正的截断行：", len(bad))
!cd /kaggle/working && cp ollama_server.log followup_outputs/ && zip -qr followup_outputs.zip followup_outputs && ls -lh followup_outputs.zip
""")
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
      "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("written", sys.argv[1])
