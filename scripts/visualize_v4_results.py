"""Visualize Benchmark v4: Fine-tuned BGE-M3 + Knowledge Graph vs Baselines.
Generates publication-quality charts and embeds them into retrieval_v4_hybrid_pipeline_report.md.
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

V3_JSON = RESULTS_DIR / "retrieval_v3_hybrid_pipeline_results.json"
V4_JSON = RESULTS_DIR / "retrieval_v3_finetuned_results.json"
REPORT_MD = RESULTS_DIR / "retrieval_v4_hybrid_pipeline_report.md"

# Load JSON results
with open(V3_JSON, "r", encoding="utf-8") as f:
    v3_data = json.load(f)

with open(V4_JSON, "r", encoding="utf-8") as f:
    v4_data = json.load(f)

# Styles & Configuration
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

# Color Palette
COLORS = {
    "base_vec": "#7f8c8d",      # Gray
    "base_hyb": "#3498db",      # Soft Blue
    "ft_vec": "#9b59b6",        # Amethyst Purple
    "ft_hyb": "#2ecc71",        # Emerald Green (Star performer)
}

LABELS = [
    "Base Vector Only",
    "Base + KG (Coupled)",
    "Fine-tuned Vector Only",
    "Fine-tuned + KG (Coupled)",
]

# -------------------------------------------------------------
# 1. Cross-Reference Subset (133 Questions) Chart
# -------------------------------------------------------------
def plot_cross_reference_comparison():
    c_b_vec = v3_data["cross_reference_subset"]["vector_only"]
    c_b_hyb = v3_data["cross_reference_subset"]["hybrid_coupled"]
    c_f_vec = v4_data["cross_reference_subset"]["finetuned_vector_only"]
    c_f_hyb = v4_data["cross_reference_subset"]["finetuned_hybrid_coupled"]

    metrics = ["Hit@1", "Recall@5", "Recall@8", "Recall@10", "MRR@10", "NDCG@10"]
    x = np.arange(len(metrics))
    width = 0.18

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)

    val_b_vec = [c_b_vec[m] * 100 if "MRR" not in m and "NDCG" not in m else c_b_vec[m] * 100 for m in metrics]
    val_b_hyb = [c_b_hyb[m] * 100 if "MRR" not in m and "NDCG" not in m else c_b_hyb[m] * 100 for m in metrics]
    val_f_vec = [c_f_vec[m] * 100 if "MRR" not in m and "NDCG" not in m else c_f_vec[m] * 100 for m in metrics]
    val_f_hyb = [c_f_hyb[m] * 100 if "MRR" not in m and "NDCG" not in m else c_f_hyb[m] * 100 for m in metrics]

    rects1 = ax.bar(x - 1.5 * width, val_b_vec, width, label="1. Base Vector Only", color=COLORS["base_vec"], alpha=0.9)
    rects2 = ax.bar(x - 0.5 * width, val_b_hyb, width, label="2. Base + KG Coupled", color=COLORS["base_hyb"], alpha=0.9)
    rects3 = ax.bar(x + 0.5 * width, val_f_vec, width, label="3. Fine-tuned Vector Only", color=COLORS["ft_vec"], alpha=0.9)
    rects4 = ax.bar(x + 1.5 * width, val_f_hyb, width, label="4. Fine-tuned + KG Coupled (Mới)", color=COLORS["ft_hyb"], alpha=0.95)

    ax.set_ylabel("Score (%) / Percentage", fontsize=12, fontweight="bold")
    ax.set_title("So Sánh Hiệu Năng Trên Nhóm Câu Hỏi Dẫn Chiếu Đa Điều Luật (133 Câu)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.legend(frameon=True, facecolor="white", edgecolor="#e0e0e0", fontsize=10, loc="upper left")

    # Add labels on top of bars
    def autolabel(rects, is_highlight=False):
        for rect in rects:
            height = rect.get_height()
            color = "#1b5e20" if is_highlight else "#333333"
            weight = "bold" if is_highlight else "normal"
            ax.annotate(f"{height:.1f}%",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, color=color, fontweight=weight)

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)
    autolabel(rects4, is_highlight=True)

    plt.tight_layout()
    out_path = PLOTS_DIR / "retrieval_v4_cross_ref_comparison.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


# -------------------------------------------------------------
# 2. Recall Progression Across Ranks (Cross-Reference Group)
# -------------------------------------------------------------
def plot_recall_progression():
    c_b_vec = v3_data["cross_reference_subset"]["vector_only"]
    c_b_hyb = v3_data["cross_reference_subset"]["hybrid_coupled"]
    c_f_vec = v4_data["cross_reference_subset"]["finetuned_vector_only"]
    c_f_hyb = v4_data["cross_reference_subset"]["finetuned_hybrid_coupled"]

    ranks = ["Rank 5 (Recall@5)", "Rank 8 (Recall@8)", "Rank 10 (Recall@10)"]
    x = np.arange(len(ranks))

    plt.figure(figsize=(10, 6), dpi=300)
    plt.plot(x, [c_b_vec["Recall@5"] * 100, c_b_vec["Recall@8"] * 100, c_b_vec["Recall@10"] * 100],
             marker="o", linewidth=2.5, markersize=8, color=COLORS["base_vec"], label="Base Vector Only")
    plt.plot(x, [c_b_hyb["Recall@5"] * 100, c_b_hyb["Recall@8"] * 100, c_b_hyb["Recall@10"] * 100],
             marker="s", linewidth=2.5, markersize=8, color=COLORS["base_hyb"], label="Base + KG (Coupled)")
    plt.plot(x, [c_f_vec["Recall@5"] * 100, c_f_vec["Recall@8"] * 100, c_f_vec["Recall@10"] * 100],
             marker="^", linewidth=2.5, markersize=8, color=COLORS["ft_vec"], label="Fine-tuned Vector Only")
    plt.plot(x, [c_f_hyb["Recall@5"] * 100, c_f_hyb["Recall@8"] * 100, c_f_hyb["Recall@10"] * 100],
             marker="D", linewidth=3.2, markersize=10, color=COLORS["ft_hyb"], label="Fine-tuned + KG Coupled (Đỉnh cao 85.44%)")

    rec_keys = ["Recall@5", "Recall@8", "Recall@10"]
    for i, k in enumerate(rec_keys):
        plt.annotate(f"{c_b_vec[k] * 100:.1f}%", (x[i], c_b_vec[k] * 100 - 3), ha="center", fontsize=9, color=COLORS["base_vec"])
        plt.annotate(f"{c_b_hyb[k] * 100:.1f}%", (x[i], c_b_hyb[k] * 100 - 3), ha="center", fontsize=9, color=COLORS["base_hyb"])
        plt.annotate(f"{c_f_vec[k] * 100:.1f}%", (x[i], c_f_vec[k] * 100 + 1.5), ha="center", fontsize=9, color=COLORS["ft_vec"])
        plt.annotate(f"{c_f_hyb[k] * 100:.1f}%", (x[i], c_f_hyb[k] * 100 + 2), ha="center", fontsize=10, fontweight="bold", color="#1b5e20")

    plt.title("Động Lực Tăng Trưởng Độ Phủ Dữ Liệu (Recall Growth Curve across Top-K)", fontsize=13, fontweight="bold", pad=15)
    plt.ylabel("Tỷ lệ thu hồi tài liệu (%)", fontsize=11, fontweight="bold")
    plt.xticks(x, ranks, fontsize=11, fontweight="bold")
    plt.ylim(35, 95)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(frameon=True, facecolor="white", edgecolor="#e0e0e0", fontsize=10, loc="lower right")

    plt.tight_layout()
    out_path = PLOTS_DIR / "retrieval_v4_recall_progression.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


# -------------------------------------------------------------
# 3. Comprehensive Dashboard (2x2 Multi-Panel Grid)
# -------------------------------------------------------------
def plot_comprehensive_dashboard():
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=300)

    # Subplot (0,0): Cross-ref Key Metrics
    ax = axes[0, 0]
    c_b_vec = v3_data["cross_reference_subset"]["vector_only"]
    c_b_hyb = v3_data["cross_reference_subset"]["hybrid_coupled"]
    c_f_hyb = v4_data["cross_reference_subset"]["finetuned_hybrid_coupled"]
    
    m_keys = ["Hit@1", "Recall@5", "Recall@10", "NDCG@10"]
    x = np.arange(len(m_keys))
    w = 0.25
    ax.bar(x - w, [c_b_vec[k] * 100 for k in m_keys], w, label="Base Vector Only", color=COLORS["base_vec"])
    ax.bar(x, [c_b_hyb[k] * 100 for k in m_keys], w, label="Base + KG (Coupled)", color=COLORS["base_hyb"])
    ax.bar(x + w, [c_f_hyb[k] * 100 for k in m_keys], w, label="Fine-tuned + KG (Mới)", color=COLORS["ft_hyb"])
    ax.set_title("A. Hiệu Năng Nhóm Dẫn Chiếu Đa Điều Luật (133 Câu)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(m_keys, fontsize=10, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Tỷ lệ (%)", fontsize=10)
    ax.legend(fontsize=9, loc="upper left")

    for i in x:
        ax.annotate(f"{c_f_hyb[m_keys[i]]*100:.1f}%", (i + w, c_f_hyb[m_keys[i]]*100 + 2), ha="center", fontsize=8, fontweight="bold", color="#1b5e20")

    # Subplot (0,1): Recall Growth Curves
    ax = axes[0, 1]
    rk = ["Top 5", "Top 8", "Top 10"]
    xr = np.arange(3)
    ax.plot(xr, [c_b_vec["Recall@5"]*100, c_b_vec["Recall@8"]*100, c_b_vec["Recall@10"]*100], marker="o", color=COLORS["base_vec"], label="Base Vector")
    ax.plot(xr, [c_b_hyb["Recall@5"]*100, c_b_hyb["Recall@8"]*100, c_b_hyb["Recall@10"]*100], marker="s", color=COLORS["base_hyb"], label="Base + KG")
    ax.plot(xr, [c_f_hyb["Recall@5"]*100, c_f_hyb["Recall@8"]*100, c_f_hyb["Recall@10"]*100], marker="D", linewidth=2.5, color=COLORS["ft_hyb"], label="Fine-tuned + KG")
    ax.set_title("B. Đường Cong Thu Hồi Recall Theo Rank (Top 5 -> Top 10)", fontsize=12, fontweight="bold")
    ax.set_xticks(xr)
    ax.set_xticklabels(rk, fontsize=10, fontweight="bold")
    ax.set_ylabel("Recall (%)", fontsize=10)
    ax.set_ylim(40, 95)
    ax.legend(fontsize=9, loc="lower right")

    # Subplot (1,0): Overall 201 Questions
    ax = axes[1, 0]
    o_b_vec = v3_data["overall"]["vector_only"]
    o_b_hyb = v3_data["overall"]["hybrid_coupled"]
    o_f_hyb = v4_data["overall"]["finetuned_hybrid_coupled"]
    o_keys = ["Hit@1", "Recall@5", "Recall@10", "NDCG@10"]
    xo = np.arange(len(o_keys))
    ax.bar(xo - w, [o_b_vec[k] * 100 for k in o_keys], w, label="Base Vector", color=COLORS["base_vec"])
    ax.bar(xo, [o_b_hyb[k] * 100 for k in o_keys], w, label="Base + KG", color=COLORS["base_hyb"])
    ax.bar(xo + w, [o_f_hyb[k] * 100 for k in o_keys], w, label="Fine-tuned + KG", color=COLORS["ft_hyb"])
    ax.set_title("C. Hiệu Năng Toàn Bộ 201 Câu Hỏi Đánh Giá", fontsize=12, fontweight="bold")
    ax.set_xticks(xo)
    ax.set_xticklabels(o_keys, fontsize=10, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Tỷ lệ (%)", fontsize=10)
    ax.legend(fontsize=9, loc="upper left")
    for i in xo:
        ax.annotate(f"{o_f_hyb[o_keys[i]]*100:.1f}%", (i + w, o_f_hyb[o_keys[i]]*100 + 2), ha="center", fontsize=8, fontweight="bold", color="#1b5e20")

    # Subplot (1,1): Precision & Rank Metric Deltas (Fine-tuned + KG vs Base Vector)
    ax = axes[1, 1]
    deltas = {
        "Hit@1 (Cross)": (c_f_hyb["Hit@1"] - c_b_vec["Hit@1"]) * 100,
        "Recall@5 (Cross)": (c_f_hyb["Recall@5"] - c_b_vec["Recall@5"]) * 100,
        "Recall@10 (Cross)": (c_f_hyb["Recall@10"] - c_b_vec["Recall@10"]) * 100,
        "NDCG@10 (Cross)": (c_f_hyb["NDCG@10"] - c_b_vec["NDCG@10"]) * 100,
        "Recall@5 (All)": (o_f_hyb["Recall@5"] - o_b_vec["Recall@5"]) * 100,
        "Recall@10 (All)": (o_f_hyb["Recall@10"] - o_b_vec["Recall@10"]) * 100,
    }
    y_pos = np.arange(len(deltas))
    bar_colors = ["#27ae60" if v > 0 else "#e74c3c" for v in deltas.values()]
    bars = ax.barh(y_pos, list(deltas.values()), color=bar_colors, alpha=0.85, height=0.55)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(list(deltas.keys()), fontsize=10, fontweight="bold")
    ax.set_xlabel("Mức tăng trưởng tuyệt đối (+%)", fontsize=10, fontweight="bold")
    ax.set_title("D. Mức Tăng Trưởng Vượt Bậc Của TH2-B-FT So Với Base Vector", fontsize=12, fontweight="bold")
    ax.axvline(0, color="#666666", linewidth=0.8)
    for bar in bars:
        w_val = bar.get_width()
        ax.annotate(f"+{w_val:.2f}%", (w_val + 0.6, bar.get_y() + bar.get_height() / 2),
                    va="center", fontsize=9, fontweight="bold", color="#1b5e20")
    ax.set_xlim(0, 35)

    plt.suptitle("TỔNG QUAN ĐỒ THỊ ĐÁNH GIÁ PIPELINE HYBRID RAG v4 (FINE-TUNED BGE-M3 + NEO4J)", fontsize=15, fontweight="bold", y=0.99)
    plt.tight_layout()
    out_path = PLOTS_DIR / "retrieval_v4_dashboard.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


def update_report_with_images():
    with open(REPORT_MD, "r", encoding="utf-8") as f:
        content = f.read()

    # Create visualization section
    vis_section = """
---

## 4. Trực Quan Hóa Đồ Thị Kết Quả Thực Nghiệm

Dưới đây là các biểu đồ trực quan hóa chi tiết các chỉ số thực nghiệm đo đạc được:

### 4.1. Biểu đồ Tổng quan Dashboard Đa Chiều (All-in-One Dashboard)
Biểu đồ tổng hợp 4 chiều phân tích: (A) Hiệu năng nhóm dẫn chiếu đa điều, (B) Đường cong thu hồi Recall, (C) Hiệu năng toàn bộ 201 câu hỏi, và (D) Mức tăng trưởng đột phá của mô hình Fine-tuned kết hợp đồ thị tri thức.

![Tổng quan Dashboard Đa Chiều](plots/retrieval_v4_dashboard.png)

---

### 4.2. So sánh Trực diện trên Phân nhóm Dẫn chiếu Đa Điều Luật (133 câu)
Biểu đồ cột so sánh trực tiếp cả 4 cấu hình (`Base Vector`, `Base + KG`, `Fine-tuned Vector`, `Fine-tuned + KG`) trên 6 chỉ số khắt khe nhất (`Hit@1`, `Recall@5`, `Recall@8`, `Recall@10`, `MRR@10`, `NDCG@10`).

![So sánh Nhóm Dẫn Chiếu](plots/retrieval_v4_cross_ref_comparison.png)

---

### 4.3. Động Lực Tăng Trưởng Độ Phủ Dữ Liệu (Recall Growth Curve)
Minh họa sự gia tăng vượt bậc của độ thu hồi Recall khi mở rộng từ Top 5 đến Top 10. Trong khi mô hình Vector thuần túy bị bão hòa ở mức thấp (55.96%), mô hình Fine-tuned kết hợp Knowledge Graph vươn tới đỉnh cao **85.44%**.

![Đường cong tăng trưởng Recall](plots/retrieval_v4_recall_progression.png)
"""

    # Insert before Section "4. Phân Tích Chuyên Sâu"
    if "## 4. Phân Tích Chuyên Sâu" in content:
        # Rename section 4 to 5
        content = content.replace("## 4. Phân Tích Chuyên Sâu", "## 5. Phân Tích Chuyên Sâu")
        content = content.replace("---\n\n## 5. Phân Tích Chuyên Sâu", vis_section + "\n---\n\n## 5. Phân Tích Chuyên Sâu")
    elif "## 5. Phân Tích Chuyên Sâu" in content:
        # Already updated, just replace the vis section
        pass
    else:
        content = content.strip() + "\n" + vis_section

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated report with embedded visualizations: {REPORT_MD}")


if __name__ == "__main__":
    plot_cross_reference_comparison()
    plot_recall_progression()
    plot_comprehensive_dashboard()
    update_report_with_images()
