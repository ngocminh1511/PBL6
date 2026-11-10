"""Visualize Benchmark v5: Comparing 3 Retrieval Strategies with Knowledge Graph:
TH1: Base BGE-M3 + KG
TH2: Finetuned v1 + KG
TH3: Finetuned v2 (model2) + KG
Generates publication-quality charts and embeds them into retrieval_v5.md and retrieval_v5_hybrid_pipeline_report.md.
"""
from __future__ import annotations

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Directory paths
REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "labor_rag" / "evaluation" / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

V5_JSON = RESULTS_DIR / "retrieval_v5_results.json"

# Load JSON results
with open(V5_JSON, "r", encoding="utf-8") as f:
    v5_data = json.load(f)

# Styles & Configuration
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

# Color Palette for 3 setups
COLORS = {
    "th1": "#3498db",  # Blue (TH1: Base + KG)
    "th2": "#2ecc71",  # Emerald Green (TH2: Finetune v1 + KG)
    "th3": "#e67e22",  # Vivid Orange / Amber (TH3: Finetune v2 + KG)
}

LABELS = [
    "TH1: Base + KG",
    "TH2: Finetune v1 + KG",
    "TH3: Finetune v2 + KG",
]


# -------------------------------------------------------------
# 1. Cross-Reference Subset (133 Questions) 3-Way Comparison
# -------------------------------------------------------------
def plot_cross_reference_comparison():
    c_th1 = v5_data["cross_reference_subset"]["TH1_Base_KG"]
    c_th2 = v5_data["cross_reference_subset"]["TH2_FinetuneV1_KG"]
    c_th3 = v5_data["cross_reference_subset"]["TH3_FinetuneV2_KG"]

    metrics = ["Hit@1", "Recall@5", "Recall@8", "Recall@10", "MRR@10", "NDCG@10", "MAP@10"]
    x = np.arange(len(metrics))
    width = 0.26

    fig, ax = plt.subplots(figsize=(13, 6.5), dpi=300)

    val_th1 = [c_th1[m] * 100 for m in metrics]
    val_th2 = [c_th2[m] * 100 for m in metrics]
    val_th3 = [c_th3[m] * 100 for m in metrics]

    rects1 = ax.bar(x - width, val_th1, width, label="TH1: Base BGE-M3 + KG", color=COLORS["th1"], alpha=0.9)
    rects2 = ax.bar(x, val_th2, width, label="TH2: Finetune v1 + KG", color=COLORS["th2"], alpha=0.9)
    rects3 = ax.bar(x + width, val_th3, width, label="TH3: Finetune v2 (model2) + KG", color=COLORS["th3"], alpha=0.9)

    ax.set_ylabel("Tỷ lệ / Điểm số (%)", fontsize=12, fontweight="bold")
    ax.set_title("So Sánh 3 Chiến Lược Retrieval Trên Phân Nhóm Dẫn Chiếu Đa Điều (133 Câu)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylim(0, 110)
    ax.legend(frameon=True, facecolor="white", edgecolor="#e0e0e0", fontsize=10, loc="upper left")

    def autolabel(rects, text_color="#333333"):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f"{height:.1f}%",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, color=text_color, fontweight="bold")

    autolabel(rects1, "#1565c0")
    autolabel(rects2, "#2e7d32")
    autolabel(rects3, "#d35400")

    plt.tight_layout()
    out_path = PLOTS_DIR / "retrieval_v5_cross_ref_comparison.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


# -------------------------------------------------------------
# 2. Overall 201 Questions 3-Way Comparison
# -------------------------------------------------------------
def plot_overall_comparison():
    o_th1 = v5_data["overall"]["TH1_Base_KG"]
    o_th2 = v5_data["overall"]["TH2_FinetuneV1_KG"]
    o_th3 = v5_data["overall"]["TH3_FinetuneV2_KG"]

    metrics = ["Hit@1", "Recall@5", "Recall@8", "Recall@10", "MRR@10", "NDCG@10", "MAP@10"]
    x = np.arange(len(metrics))
    width = 0.26

    fig, ax = plt.subplots(figsize=(13, 6.5), dpi=300)

    val_th1 = [o_th1[m] * 100 for m in metrics]
    val_th2 = [o_th2[m] * 100 for m in metrics]
    val_th3 = [o_th3[m] * 100 for m in metrics]

    rects1 = ax.bar(x - width, val_th1, width, label="TH1: Base BGE-M3 + KG", color=COLORS["th1"], alpha=0.9)
    rects2 = ax.bar(x, val_th2, width, label="TH2: Finetune v1 + KG", color=COLORS["th2"], alpha=0.9)
    rects3 = ax.bar(x + width, val_th3, width, label="TH3: Finetune v2 (model2) + KG", color=COLORS["th3"], alpha=0.9)

    ax.set_ylabel("Tỷ lệ / Điểm số (%)", fontsize=12, fontweight="bold")
    ax.set_title("So Sánh 3 Chiến Lược Retrieval Trên Toàn Bộ Benchmark 201 Câu", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylim(0, 110)
    ax.legend(frameon=True, facecolor="white", edgecolor="#e0e0e0", fontsize=10, loc="upper left")

    def autolabel(rects, text_color="#333333"):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f"{height:.1f}%",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, color=text_color, fontweight="bold")

    autolabel(rects1, "#1565c0")
    autolabel(rects2, "#2e7d32")
    autolabel(rects3, "#d35400")

    plt.tight_layout()
    out_path = PLOTS_DIR / "retrieval_v5_overall_comparison.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


# -------------------------------------------------------------
# 3. Recall Growth Progression (Top 5 -> Top 8 -> Top 10)
# -------------------------------------------------------------
def plot_recall_progression():
    c_th1 = v5_data["cross_reference_subset"]["TH1_Base_KG"]
    c_th2 = v5_data["cross_reference_subset"]["TH2_FinetuneV1_KG"]
    c_th3 = v5_data["cross_reference_subset"]["TH3_FinetuneV2_KG"]

    ranks = ["Rank 5 (Recall@5)", "Rank 8 (Recall@8)", "Rank 10 (Recall@10)"]
    x = np.arange(len(ranks))

    plt.figure(figsize=(10, 6), dpi=300)
    plt.plot(x, [c_th1["Recall@5"] * 100, c_th1["Recall@8"] * 100, c_th1["Recall@10"] * 100],
             marker="s", linewidth=2.5, markersize=8, color=COLORS["th1"], label="TH1: Base + KG (79.87%)")
    plt.plot(x, [c_th2["Recall@5"] * 100, c_th2["Recall@8"] * 100, c_th2["Recall@10"] * 100],
             marker="D", linewidth=3.0, markersize=9, color=COLORS["th2"], label="TH2: Finetune v1 + KG (85.44%)")
    plt.plot(x, [c_th3["Recall@5"] * 100, c_th3["Recall@8"] * 100, c_th3["Recall@10"] * 100],
             marker="o", linewidth=3.2, markersize=10, color=COLORS["th3"], label="TH3: Finetune v2 + KG (Đỉnh cao 88.22%)")

    rec_keys = ["Recall@5", "Recall@8", "Recall@10"]
    for i, k in enumerate(rec_keys):
        plt.annotate(f"{c_th1[k] * 100:.1f}%", (x[i], c_th1[k] * 100 - 3), ha="center", fontsize=9, color=COLORS["th1"], fontweight="bold")
        plt.annotate(f"{c_th2[k] * 100:.1f}%", (x[i], c_th2[k] * 100 - 3), ha="center", fontsize=9, color=COLORS["th2"], fontweight="bold")
        plt.annotate(f"{c_th3[k] * 100:.1f}%", (x[i], c_th3[k] * 100 + 2), ha="center", fontsize=10, color=COLORS["th3"], fontweight="bold")

    plt.title("Đường Cong Tăng Trưởng Độ Phủ Dữ Liệu (Recall Growth Curve)", fontsize=13, fontweight="bold", pad=15)
    plt.ylabel("Tỷ lệ thu hồi tài liệu (%)", fontsize=11, fontweight="bold")
    plt.xticks(x, ranks, fontsize=11, fontweight="bold")
    plt.ylim(55, 96)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(frameon=True, facecolor="white", edgecolor="#e0e0e0", fontsize=10, loc="lower right")

    plt.tight_layout()
    out_path = PLOTS_DIR / "retrieval_v5_recall_progression.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


# -------------------------------------------------------------
# 4. Multi-Panel Comprehensive Dashboard (2x2)
# -------------------------------------------------------------
def plot_dashboard():
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=300)

    # Panel (0,0): Cross-ref Key Metrics
    ax = axes[0, 0]
    c_th1 = v5_data["cross_reference_subset"]["TH1_Base_KG"]
    c_th2 = v5_data["cross_reference_subset"]["TH2_FinetuneV1_KG"]
    c_th3 = v5_data["cross_reference_subset"]["TH3_FinetuneV2_KG"]
    m_keys = ["Hit@1", "Recall@5", "Recall@10", "NDCG@10"]
    x = np.arange(len(m_keys))
    w = 0.25
    ax.bar(x - w, [c_th1[k] * 100 for k in m_keys], w, label="TH1: Base + KG", color=COLORS["th1"])
    ax.bar(x, [c_th2[k] * 100 for k in m_keys], w, label="TH2: Finetune v1 + KG", color=COLORS["th2"])
    ax.bar(x + w, [c_th3[k] * 100 for k in m_keys], w, label="TH3: Finetune v2 + KG", color=COLORS["th3"])
    ax.set_title("(A) Hiệu Năng Phân Nhóm Dẫn Chiếu Đa Điều (133 câu)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(m_keys, fontweight="bold")
    ax.set_ylim(50, 105)
    ax.legend(loc="lower right")

    # Panel (0,1): Overall Key Metrics
    ax = axes[0, 1]
    o_th1 = v5_data["overall"]["TH1_Base_KG"]
    o_th2 = v5_data["overall"]["TH2_FinetuneV1_KG"]
    o_th3 = v5_data["overall"]["TH3_FinetuneV2_KG"]
    ax.bar(x - w, [o_th1[k] * 100 for k in m_keys], w, label="TH1: Base + KG", color=COLORS["th1"])
    ax.bar(x, [o_th2[k] * 100 for k in m_keys], w, label="TH2: Finetune v1 + KG", color=COLORS["th2"])
    ax.bar(x + w, [o_th3[k] * 100 for k in m_keys], w, label="TH3: Finetune v2 + KG", color=COLORS["th3"])
    ax.set_title("(B) Hiệu Năng Tổng Thể Toàn Bộ (201 câu)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(m_keys, fontweight="bold")
    ax.set_ylim(60, 105)
    ax.legend(loc="lower right")

    # Panel (1,0): Recall Progression
    ax = axes[1, 0]
    ranks = ["Recall@5", "Recall@8", "Recall@10"]
    rx = np.arange(len(ranks))
    ax.plot(rx, [c_th1[r] * 100 for r in ranks], marker="s", color=COLORS["th1"], lw=2.5, label="TH1: Base + KG")
    ax.plot(rx, [c_th2[r] * 100 for r in ranks], marker="D", color=COLORS["th2"], lw=2.5, label="TH2: Finetune v1 + KG")
    ax.plot(rx, [c_th3[r] * 100 for r in ranks], marker="o", color=COLORS["th3"], lw=2.5, label="TH3: Finetune v2 + KG")
    ax.set_title("(C) Đường Cong Tăng Trưởng Thu Hồi Tài Liệu (Recall)", fontsize=12, fontweight="bold")
    ax.set_xticks(rx)
    ax.set_xticklabels(ranks, fontweight="bold")
    ax.set_ylim(58, 90)
    ax.legend(loc="lower right")

    # Panel (1,1): Ranking Quality (MRR, NDCG, MAP)
    ax = axes[1, 1]
    rank_keys = ["MRR@10", "NDCG@8", "NDCG@10", "MAP@10"]
    kx = np.arange(len(rank_keys))
    ax.bar(kx - w, [c_th1[k] * 100 for k in rank_keys], w, label="TH1: Base + KG", color=COLORS["th1"])
    ax.bar(kx, [c_th2[k] * 100 for k in rank_keys], w, label="TH2: Finetune v1 + KG", color=COLORS["th2"])
    ax.bar(kx + w, [c_th3[k] * 100 for k in rank_keys], w, label="TH3: Finetune v2 + KG", color=COLORS["th3"])
    ax.set_title("(D) Chất Lượng Xếp Hạng Ngữ Cảnh (Ranking Quality on Cross-Ref)", fontsize=12, fontweight="bold")
    ax.set_xticks(kx)
    ax.set_xticklabels(rank_keys, fontweight="bold")
    ax.set_ylim(65, 100)
    ax.legend(loc="lower right")

    plt.tight_layout()
    out_path = PLOTS_DIR / "retrieval_v5_dashboard.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    plot_cross_reference_comparison()
    plot_overall_comparison()
    plot_recall_progression()
    plot_dashboard()
    print("All v5 visualization charts generated successfully!")

