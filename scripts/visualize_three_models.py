"""Visualize Benchmark Results for 3 Base Embedding Models with Knowledge Graph:
1. BGE-M3 (Base + KG)
2. BKAI (Base + KG)
3. MPNet (Base + KG)
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "labor_rag" / "evaluation" / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

JSON_PATH = RESULTS_DIR / "retrieval_three_models_comparison_results.json"
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

COLORS = {
    "bge": "#1f77b4",   # Strong Blue (BGE-M3)
    "bkai": "#ff7f0e",  # Orange (BKAI)
    "mpnet": "#2ca02c", # Green (MPNet)
}

# 1. Overall Comparison 3-Way (Base + KG)
def plot_overall_comparison():
    ov = data["overall"]
    metrics = ["Hit@1", "Hit@5", "Recall@5", "Recall@10", "MRR@10", "NDCG@10", "MAP@10"]
    x = np.arange(len(metrics))
    width = 0.26

    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=300)

    bge_k = [ov["BGE_Base_KG"][m] for m in metrics]
    bkai_k = [ov["BKAI_Base_KG"][m] for m in metrics]
    mpnet_k = [ov["MPNet_Base_KG"][m] for m in metrics]

    rects1 = ax.bar(x - width, bge_k, width, label="BGE-M3 Base + KG", color=COLORS["bge"], alpha=0.95)
    rects2 = ax.bar(x, bkai_k, width, label="BKAI Base + KG", color=COLORS["bkai"], alpha=0.95)
    rects3 = ax.bar(x + width, mpnet_k, width, label="MPNet Base + KG", color=COLORS["mpnet"], alpha=0.95)

    ax.set_title("So Sánh Đối Đầu 3 Mô Hình Embedding Kết Hợp Knowledge Graph (201 Câu Hỏi)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylabel("Điểm số / Tỷ lệ", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=11)

    for rects in [rects1, rects2, rects3]:
        for r in rects:
            h = r.get_height()
            ax.annotate(f"{h * 100:.1f}%" if h <= 1.0 and "Hit" in metrics[int(round(r.get_x()))] or "Recall" in metrics[int(round(r.get_x()))] else f"{h:.3f}",
                        xy=(r.get_x() + r.get_width() / 2, h),
                        xytext=(0, 4), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.5, rotation=90)

    fig.tight_layout()
    out = PLOTS_DIR / "retrieval_three_models_overall.png"
    plt.savefig(out)
    plt.close()
    print(f"Saved {out}")

# 2. Cross-reference Comparison
def plot_cross_ref_comparison():
    cr = data["cross_reference_subset"]
    metrics = ["Hit@1", "Recall@5", "Recall@8", "Recall@10", "MRR@10", "NDCG@10", "MAP@10"]
    x = np.arange(len(metrics))
    width = 0.26

    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=300)

    bge_k = [cr["BGE_Base_KG"][m] for m in metrics]
    bkai_k = [cr["BKAI_Base_KG"][m] for m in metrics]
    mpnet_k = [cr["MPNet_Base_KG"][m] for m in metrics]

    rects1 = ax.bar(x - width, bge_k, width, label="BGE-M3 Base + KG", color=COLORS["bge"], alpha=0.95)
    rects2 = ax.bar(x, bkai_k, width, label="BKAI Base + KG", color=COLORS["bkai"], alpha=0.95)
    rects3 = ax.bar(x + width, mpnet_k, width, label="MPNet Base + KG", color=COLORS["mpnet"], alpha=0.95)

    ax.set_title("Phân Nhóm Dẫn Chiếu Đa Điều Luật (133 Câu): So Sánh 3 Mô Hình Embedding + KG", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylabel("Điểm số / Tỷ lệ", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=11)

    for rects in [rects1, rects2, rects3]:
        for r in rects:
            h = r.get_height()
            ax.annotate(f"{h * 100:.1f}%" if h <= 1.0 and "Hit" in metrics[int(round(r.get_x()))] or "Recall" in metrics[int(round(r.get_x()))] else f"{h:.3f}",
                        xy=(r.get_x() + r.get_width() / 2, h),
                        xytext=(0, 4), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.5, rotation=90)

    fig.tight_layout()
    out = PLOTS_DIR / "retrieval_three_models_cross_ref.png"
    plt.savefig(out)
    plt.close()
    print(f"Saved {out}")

# 3. Recall Progression Curve
def plot_recall_progression():
    cr = data["cross_reference_subset"]
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    cutoffs = [5, 8, 10]

    bge_k = [cr["BGE_Base_KG"][f"Recall@{k}"] * 100 for k in cutoffs]
    bkai_k = [cr["BKAI_Base_KG"][f"Recall@{k}"] * 100 for k in cutoffs]
    mpnet_k = [cr["MPNet_Base_KG"][f"Recall@{k}"] * 100 for k in cutoffs]

    ax.plot(cutoffs, bge_k, "s-", color=COLORS["bge"], linewidth=2.5, markersize=8, label="BGE-M3 Base + KG")
    ax.plot(cutoffs, bkai_k, "D-", color=COLORS["bkai"], linewidth=2.5, markersize=8, label="BKAI Base + KG")
    ax.plot(cutoffs, mpnet_k, "o-", color=COLORS["mpnet"], linewidth=2.5, markersize=8, label="MPNet Base + KG")

    for k, v in zip(cutoffs, bge_k):
        ax.annotate(f"{v:.1f}%", (k, v), textcoords="offset points", xytext=(0, 8), ha="center", fontweight="bold", color=COLORS["bge"])
    for k, v in zip(cutoffs, bkai_k):
        ax.annotate(f"{v:.1f}%", (k, v), textcoords="offset points", xytext=(0, 8), ha="center", fontweight="bold", color=COLORS["bkai"])
    for k, v in zip(cutoffs, mpnet_k):
        ax.annotate(f"{v:.1f}%", (k, v), textcoords="offset points", xytext=(0, -14), ha="center", fontweight="bold", color=COLORS["mpnet"])

    ax.set_title("Đường Cong Tăng Trưởng Độ Phủ Dẫn Chiếu Recall (Top 5 -> Top 10)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Top K", fontsize=11, fontweight="bold")
    ax.set_ylabel("Recall (%)", fontsize=11, fontweight="bold")
    ax.set_xticks(cutoffs)
    ax.set_ylim(15, 95)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=11)

    fig.tight_layout()
    out = PLOTS_DIR / "retrieval_three_models_recall_progression.png"
    plt.savefig(out)
    plt.close()
    print(f"Saved {out}")

if __name__ == "__main__":
    plot_overall_comparison()
    plot_cross_ref_comparison()
    plot_recall_progression()

