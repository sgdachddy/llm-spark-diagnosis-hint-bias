"""把下面的单元格拼成 Kaggle 可直接导入的 .ipynb。用法：python3 build_notebook.py <输出路径>"""
import json
import sys

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")})


def code(text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                  "outputs": [], "source": text.strip("\n")})


md(r"""
# 用户错误猜测会不会带偏模型：Ollama 批量运行

**运行前在右侧 Settings 里设置：**
1. Accelerator 选 **GPU T4 x2**（或 P100）
2. Internet 打开 **On**（需要先完成手机号验证）

**推荐跑法：** 先手动运行第 1–4 个单元格确认环境正常，再点右上角 **Save Version → Save & Run All (Commit)**，让它在后台跑完。跑完后在该版本的 **Output** 页下载 `outputs.zip`。

脚本支持断点续跑：已经存在的结果文件会自动跳过。
""")

code(r"""
# ===== 0. 参数（只需要改这里） =====
REPO_URL = ""            # 你的 GitHub 仓库地址，例如 "https://github.com/<用户名>/llm-spark-diagnosis-hint-bias"
                         # 留空则改为在 /kaggle/input 里查找上传的 prompts 数据集
MODEL = "qwen2.5:7b"     # 约 4.7 GB，T4 显存足够；中文能力较好
REPS = 5                 # 每个提示词重复次数
NUM_CTX = 16384          # 上下文窗口。默认值很小，证据会被悄悄截断，必须设大
NUM_PREDICT = 2048       # 单次回答的最大输出 token，防止无限输出
BASE_SEED = 20261118     # 记录随机种子，便于复现；温度保持模型默认值，不手动调低
OUT_DIR = "/kaggle/working/outputs/ollama"
""")

code(r"""
# ===== 1. 检查 GPU =====
!nvidia-smi
""")

code(r"""
# ===== 2. 安装并启动 Ollama =====
!apt-get -qq update > /dev/null && apt-get -qq install -y zstd pciutils lshw > /dev/null
!curl -fsSL https://ollama.com/install.sh | sh

import subprocess, time, requests, os
server_log = open("/kaggle/working/ollama_server.log", "w")
server = subprocess.Popen(["ollama", "serve"], stdout=server_log, stderr=subprocess.STDOUT)

for _ in range(60):
    try:
        requests.get("http://127.0.0.1:11434/api/version", timeout=2)
        break
    except Exception:
        time.sleep(1)
print("Ollama version:", requests.get("http://127.0.0.1:11434/api/version").json())
""")

code(r"""
# ===== 3. 下载模型 =====
!ollama pull {MODEL}
!ollama list
""")

code(r"""
# ===== 4. 读取 24 个提示词 =====
import glob, re
from pathlib import Path

if REPO_URL:
    subprocess.run(["rm", "-rf", "/kaggle/working/repo"], check=True)
    subprocess.run(["git", "clone", "-q", REPO_URL, "/kaggle/working/repo"], check=True)
    search_root = "/kaggle/working/repo"
else:
    search_root = "/kaggle/input"

prompt_files = sorted(p for p in glob.glob(f"{search_root}/**/case*_A*_B*.md", recursive=True)
                      if re.search(r"case\d_A[12]_B[012]\.md$", p))
prompts = {Path(p).stem: Path(p).read_text(encoding="utf-8") for p in prompt_files}
print(f"找到 {len(prompts)} 个提示词")
assert len(prompts) == 24, "应当是 24 个提示词，请检查 REPO_URL 或上传的数据集"
print("示例：", list(prompts)[:3])
""")

code(r"""
# ===== 5. 冒烟测试：只跑 1 次，看看回答是否正常 =====
def ask(prompt_text, seed):
    r = requests.post("http://127.0.0.1:11434/api/chat", json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt_text}],
        "stream": False,
        "options": {"num_ctx": NUM_CTX, "num_predict": NUM_PREDICT, "seed": seed},
    }, timeout=900)
    r.raise_for_status()
    return r.json()

t0 = time.time()
test = ask(prompts["case1_A2_B1"], seed=1)
print(f"用时 {time.time() - t0:.1f} s，输入 token {test.get('prompt_eval_count')}，输出 token {test.get('eval_count')}")
print(test["message"]["content"][:1500])
""")

code(r"""
# ===== 6. 正式批量运行（4 病例 × 6 条件 × REPS 次） =====
import json, random

os.makedirs(OUT_DIR, exist_ok=True)
log_path = "/kaggle/working/outputs/ollama_runs.jsonl"
names = sorted(prompts)
total = len(names) * REPS
done = 0
start = time.time()

for rep in range(1, REPS + 1):
    order = names[:]
    random.Random(BASE_SEED + rep).shuffle(order)   # 每轮打乱顺序，减少顺序效应
    for name in order:
        out_file = Path(OUT_DIR) / f"{name}_r{rep}.md"
        done += 1
        if out_file.exists():
            continue                                  # 断点续跑
        seed = BASE_SEED + rep * 100 + names.index(name)
        for attempt in range(3):
            try:
                res = ask(prompts[name], seed)
                break
            except Exception as e:
                print(f"{name} r{rep} 第 {attempt + 1} 次失败：{e}")
                time.sleep(10)
        else:
            continue
        answer = res["message"]["content"]
        meta = {
            "file": out_file.name, "prompt": name, "rep": rep, "seed": seed, "model": MODEL,
            "num_ctx": NUM_CTX, "prompt_eval_count": res.get("prompt_eval_count"),
            "eval_count": res.get("eval_count"), "total_duration_s": round(res.get("total_duration", 0) / 1e9, 1),
            "done_reason": res.get("done_reason"),
        }
        out_file.write_text(
            f"<!-- {json.dumps(meta, ensure_ascii=False)} -->\n\n{answer}\n", encoding="utf-8")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        elapsed = time.time() - start
        print(f"[{done}/{total}] {name} r{rep}  {meta['total_duration_s']} s  已用 {elapsed / 60:.1f} min")

print("全部完成")
""")

code(r"""
# ===== 7. 质量检查：有没有截断、有没有输出被砍断 =====
server_log.flush()
log_text = Path("/kaggle/working/ollama_server.log").read_text(errors="ignore")
truncation_lines = [l for l in log_text.splitlines() if "truncat" in l.lower()]
print("服务器日志中的截断警告：", len(truncation_lines))
for l in truncation_lines[:5]:
    print("  ", l)

runs = [json.loads(l) for l in open(log_path, encoding="utf-8")]
cut = [r["file"] for r in runs if r.get("done_reason") == "length"]
print(f"共 {len(runs)} 条记录；因达到 NUM_PREDICT 上限而被砍断的回答：{len(cut)}", cut[:10])
print("结果文件数：", len(list(Path(OUT_DIR).glob('*.md'))))
""")

code(r"""
# ===== 8. 打包下载 =====
!cd /kaggle/working && cp ollama_server.log outputs/ && zip -qr outputs.zip outputs && ls -lh outputs.zip
""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("written", sys.argv[1])
