"""Visualize BKAI vs BGE-M3 Benchmark Results with Knowledge Graph."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "labor_rag" / "evaluation" / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

JSON_PATH = RESULTS_DIR / "retrieval_bkai_vs_bge_results.json"
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

COLORS = {
    "bge_vec": "#7f8c8d",   # Gray
    "bge_kg": "#2980b9",    # Strong Blue
    "bkai_vec": "#bdc3c7",  # Light Gray
    "bkai_kg": "#e67e22",   # Vivid Orange
}

# 1. Overall Comparison Bar Chart
def plot_overall_comparison():
    ov = data["overall"]
    metrics = ["Hit@1", "Hit@5", "Recall@5", "Recall@10", "MRR@10", "NDCG@10", "MAP@10"]
    x = np.arange(len(metrics))
    width = 0.20

    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=300)

    bge_v = [ov["BGE_Vector_Only"][m] for m in metrics]
    bge_k = [ov["BGE_Base_KG"][m] for m in metrics]
    bkai_v = [ov["BKAI_Vector_Only"][m] for m in metrics]
    bkai_k = [ov["BKAI_Base_KG"][m] for m in metrics]

    rects1 = ax.bar(x - 1.5 * width, bge_v, width, label="BGE-M3 Vector Only", color=COLORS["bge_vec"], alpha=0.85)
    rects2 = ax.bar(x - 0.5 * width, bge_k, width, label="BGE-M3 Base + KG", color=COLORS["bge_kg"], alpha=0.95)
    rects3 = ax.bar(x + 0.5 * width, bkai_v, width, label="BKAI Vector Only", color=COLORS["bkai_vec"], alpha=0.85)
    rects4 = ax.bar(x + 1.5 * width, bkai_k, width, label="BKAI Base + KG", color=COLORS["bkai_kg"], alpha=0.95)

    ax.set_title("Benchmark Retrieval Toàn Diện (201 Câu Hỏi): BGE-M3 vs BKAI (Base + KG)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylabel("Điểm số / Tỷ lệ", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=10)

    for rects in [rects1, rects2, rects3, rects4]:
        for r in rects:
            h = r.get_height()
            ax.annotate(f"{h * 100:.1f}%" if h <= 1.0 else f"{h:.3f}",
                        xy=(r.get_x() + r.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, rotation=90)

    fig.tight_layout()
    out = PLOTS_DIR / "retrieval_bkai_vs_bge_overall.png"
    plt.savefig(out)
    plt.close()
    print(f"Saved {out}")

# 2. Cross-reference Comparison
def plot_cross_ref_comparison():
    cr = data["cross_reference_subset"]
    metrics = ["Hit@1", "Recall@5", "Recall@8", "Recall@10", "MRR@10", "NDCG@10", "MAP@10"]
    x = np.arange(len(metrics))
    width = 0.20

    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=300)

    bge_v = [cr["BGE_Vector_Only"][m] for m in metrics]
    bge_k = [cr["BGE_Base_KG"][m] for m in metrics]
    bkai_v = [cr["BKAI_Vector_Only"][m] for m in metrics]
    bkai_k = [cr["BKAI_Base_KG"][m] for m in metrics]

    rects1 = ax.bar(x - 1.5 * width, bge_v, width, label="BGE-M3 Vector Only", color=COLORS["bge_vec"], alpha=0.85)
    rects2 = ax.bar(x - 0.5 * width, bge_k, width, label="BGE-M3 Base + KG", color=COLORS["bge_kg"], alpha=0.95)
    rects3 = ax.bar(x + 0.5 * width, bkai_v, width, label="BKAI Vector Only", color=COLORS["bkai_vec"], alpha=0.85)
    rects4 = ax.bar(x + 1.5 * width, bkai_k, width, label="BKAI Base + KG", color=COLORS["bkai_kg"], alpha=0.95)

    ax.set_title("Phân Nhóm Dẫn Chiếu Đa Điều Luật (133 Câu): BGE-M3 vs BKAI (Base + KG)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylabel("Điểm số / Tỷ lệ", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=10)

    for rects in [rects1, rects2, rects3, rects4]:
        for r in rects:
            h = r.get_height()
            ax.annotate(f"{h * 100:.1f}%" if h <= 1.0 else f"{h:.3f}",
                        xy=(r.get_x() + r.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, rotation=90)

    fig.tight_layout()
    out = PLOTS_DIR / "retrieval_bkai_vs_bge_cross_ref.png"
    plt.savefig(out)
    plt.close()
    print(f"Saved {out}")

# 3. Recall Progression Curve
def plot_recall_progression():
    cr = data["cross_reference_subset"]
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    cutoffs = [5, 8, 10]

    bge_v = [cr["BGE_Vector_Only"][f"Recall@{k}"] * 100 for k in cutoffs]
    bge_k = [cr["BGE_Base_KG"][f"Recall@{k}"] * 100 for k in cutoffs]
    bkai_v = [cr["BKAI_Vector_Only"][f"Recall@{k}"] * 100 for k in cutoffs]
    bkai_k = [cr["BKAI_Base_KG"][f"Recall@{k}"] * 100 for k in cutoffs]

    ax.plot(cutoffs, bge_v, "o--", color=COLORS["bge_vec"], linewidth=2, label="BGE-M3 Vector Only")
    ax.plot(cutoffs, bge_k, "s-", color=COLORS["bge_kg"], linewidth=2.5, label="BGE-M3 Base + KG")
    ax.plot(cutoffs, bkai_v, "^--", color=COLORS["bkai_vec"], linewidth=2, label="BKAI Vector Only")
    ax.plot(cutoffs, bkai_k, "D-", color=COLORS["bkai_kg"], linewidth=2.5, label="BKAI Base + KG")

    for k, v in zip(cutoffs, bge_k):
        ax.annotate(f"{v:.1f}%", (k, v), textcoords="offset points", xytext=(0, 8), ha="center", fontweight="bold", color=COLORS["bge_kg"])
    for k, v in zip(cutoffs, bkai_k):
        ax.annotate(f"{v:.1f}%", (k, v), textcoords="offset points", xytext=(0, 8), ha="center", fontweight="bold", color=COLORS["bkai_kg"])

    ax.set_title("Đường Cong Tăng Trưởng Độ Phủ Dữ Liệu (Recall Progression - Top 5 đến Top 10)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Top K", fontsize=11, fontweight="bold")
    ax.set_ylabel("Recall (%)", fontsize=11, fontweight="bold")
    ax.set_xticks(cutoffs)
    ax.set_ylim(20, 95)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=10)

    fig.tight_layout()
    out = PLOTS_DIR / "retrieval_bkai_vs_bge_recall_progression.png"
    plt.savefig(out)
    plt.close()
    print(f"Saved {out}")

if __name__ == "__main__":
    plot_overall_comparison()
    plot_cross_ref_comparison()
    plot_recall_progression()

