"""Script to generate publication-quality visual charts for retrieval benchmarks.

Produces:
1. labor_rag/evaluation/results/retrieval_benchmark_chart.png (Overall comparison across 4 configurations)
2. labor_rag/evaluation/results/recall_boost_chart.png (Knowledge Graph impact on Recall@10)
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_JSON = REPO_ROOT / "labor_rag" / "evaluation" / "results" / "retrieval_hybrid_graph_results.json"
OUT_DIR = REPO_ROOT / "labor_rag" / "evaluation" / "results"

# Load benchmark data
with open(RESULTS_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)["benchmarks"]

# Set clean scientific plotting style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.size"] = 11

def plot_comprehensive_benchmark():
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)

    metrics = ["Hit@1", "Hit@5", "Recall@5", "Recall@10", "MRR@10", "nDCG@10"]
    labels_vi = ["Hit@1\n(Top-1 đúng)", "Hit@5\n(Top-5 đúng)", "Recall@5\n(Độ phủ Top-5)", "Recall@10\n(Độ phủ Top-10)", "MRR@10\n(Độ sớm KQ)", "nDCG@10\n(Xếp hạng đa cấp)"]
    
    x = np.arange(len(metrics))
    width = 0.20

    # Data series
    th1_vec = [data["TH1_minimal_vector_only"]["Hit@1"], data["TH1_minimal_vector_only"]["Hit@5"], data["TH1_minimal_vector_only"]["Recall@5"], data["TH1_minimal_vector_only"]["Recall@10"], data["TH1_minimal_vector_only"]["MRR@10"], data["TH1_minimal_vector_only"]["NDCG@10"]]
    th1_hyb = [data["TH1_minimal_hybrid"]["Hit@1"], data["TH1_minimal_hybrid"]["Hit@5"], data["TH1_minimal_hybrid"]["Recall@5"], data["TH1_minimal_hybrid"]["Recall@10"], data["TH1_minimal_hybrid"]["MRR@10"], data["TH1_minimal_hybrid"]["NDCG@10"]]
    th2_vec = [data["TH2_full_vector_only"]["Hit@1"], data["TH2_full_vector_only"]["Hit@5"], data["TH2_full_vector_only"]["Recall@5"], data["TH2_full_vector_only"]["Recall@10"], data["TH2_full_vector_only"]["MRR@10"], data["TH2_full_vector_only"]["NDCG@10"]]
    th2_hyb = [data["TH2_full_hybrid"]["Hit@1"], data["TH2_full_hybrid"]["Hit@5"], data["TH2_full_hybrid"]["Recall@5"], data["TH2_full_hybrid"]["Recall@10"], data["TH2_full_hybrid"]["MRR@10"], data["TH2_full_hybrid"]["NDCG@10"]]

    colors = ["#7fb3d5", "#2471a3", "#f8c471", "#d35400"]

    rects1 = ax.bar(x - 1.5 * width, [v * 100 for v in th1_vec], width, label="TH1 (Minimal) - Vector Only", color=colors[0], edgecolor="white", linewidth=1.2)
    rects2 = ax.bar(x - 0.5 * width, [v * 100 for v in th1_hyb], width, label="TH1 (Minimal) + Knowledge Graph", color=colors[1], edgecolor="white", linewidth=1.2)
    rects3 = ax.bar(x + 0.5 * width, [v * 100 for v in th2_vec], width, label="TH2 (Full Context) - Vector Only", color=colors[2], edgecolor="white", linewidth=1.2)
    rects4 = ax.bar(x + 1.5 * width, [v * 100 for v in th2_hyb], width, label="TH2 (Full Context) + Knowledge Graph", color=colors[3], edgecolor="white", linewidth=1.2)

    ax.set_ylabel("Điểm số (%)", fontsize=13, fontweight="bold", labelpad=10)
    ax.set_title("So Sánh Hiệu Năng Truy Xuất: TH1 vs TH2 & Vector vs Knowledge Graph (Hybrid RAG)", fontsize=15, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels_vi, fontsize=11, fontweight="bold")
    ax.set_ylim(0, 110)
    ax.legend(loc="upper right", frameon=True, framealpha=0.95, fontsize=11, shadow=True)

    # Add value labels on top of bars
    def autolabel(rects, is_highlight=False):
        for rect in rects:
            height = rect.get_height()
            fontweight = "bold" if is_highlight else "normal"
            ax.annotate(f"{height:.1f}%",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha="center", va="bottom",
                        fontsize=8.5, fontweight=fontweight)

    autolabel(rects1)
    autolabel(rects2, is_highlight=True)
    autolabel(rects3)
    autolabel(rects4, is_highlight=True)

    plt.tight_layout()
    chart_path = OUT_DIR / "retrieval_benchmark_chart.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    print(f"[OK] Saved comprehensive benchmark chart to: {chart_path}")


def plot_recall_and_latency():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)

    # Subplot 1: Recall@10 Boost (Đòn bẩy Knowledge Graph)
    cases = ["TH1 (Minimal Text)", "TH2 (Full Context)"]
    vec_recall = [data["TH1_minimal_vector_only"]["Recall@10"] * 100, data["TH2_full_vector_only"]["Recall@10"] * 100]
    hyb_recall = [data["TH1_minimal_hybrid"]["Recall@10"] * 100, data["TH2_full_hybrid"]["Recall@10"] * 100]

    x = np.arange(len(cases))
    width = 0.35

    bar1 = ax1.bar(x - width/2, vec_recall, width, label="Vector Search thuần túy", color="#aed6f1", edgecolor="#2874a6", linewidth=1.5)
    bar2 = ax1.bar(x + width/2, hyb_recall, width, label="Vector + Knowledge Graph (Hybrid)", color="#2874a6", edgecolor="#1b4f72", linewidth=1.5)

    ax1.set_ylabel("Độ phủ thông tin Recall@10 (%)", fontsize=12, fontweight="bold")
    ax1.set_title("Đột Phá Về Recall@10 Khi Tích Hợp Knowledge Graph", fontsize=13, fontweight="bold", pad=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(cases, fontsize=12, fontweight="bold")
    ax1.set_ylim(0, 90)
    ax1.legend(loc="upper left", frameon=True, fontsize=10.5)

    # Highlight growth arrows & text
    for i in range(len(cases)):
        diff = hyb_recall[i] - vec_recall[i]
        ax1.annotate(f"+{diff:.1f}%\n(Tăng vọt)",
                    xy=(x[i] + width/2, hyb_recall[i]),
                    xytext=(0, 6),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=10.5, fontweight="bold", color="#b03a2e")

    for bar in bar1 + bar2:
        h = bar.get_height()
        ax1.annotate(f"{h:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, h / 2),
                    ha="center", va="center",
                    fontsize=10, fontweight="bold", color="black" if bar in bar1 else "white")

    # Subplot 2: Latency Breakdown (ms)
    lat_labels = ["TH1: Vector Only", "TH1: + Graph KG", "TH2: Vector Only", "TH2: + Graph KG"]
    lat_values = [
        data["TH1_minimal_vector_only"]["avg_latency_ms"],
        data["TH1_minimal_hybrid"]["avg_latency_ms"],
        data["TH2_full_vector_only"]["avg_latency_ms"],
        data["TH2_full_hybrid"]["avg_latency_ms"],
    ]
    colors = ["#7fb3d5", "#2471a3", "#f8c471", "#d35400"]
    bars_lat = ax2.bar(lat_labels, lat_values, width=0.55, color=colors, edgecolor="gray", linewidth=1)

    ax2.set_ylabel("Thời gian phản hồi (mili-giây / ms)", fontsize=12, fontweight="bold")
    ax2.set_title("So Sánh Độ Trễ Truy Vấn (Search Latency)", fontsize=13, fontweight="bold", pad=12)
    ax2.set_ylim(0, 650)
    ax2.set_xticklabels(lat_labels, rotation=15, ha="right", fontsize=10, fontweight="bold")

    # Add standard real-time threshold line
    ax2.axhline(500, color="red", linestyle="--", alpha=0.7, label="Ngưỡng Real-time tiêu chuẩn (<500ms)")
    ax2.legend(loc="upper left", frameon=True, fontsize=10)

    for bar in bars_lat:
        h = bar.get_height()
        ax2.annotate(f"{h:.1f} ms",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=10, fontweight="bold")

    plt.tight_layout()
    chart_path = OUT_DIR / "recall_and_latency_chart.png"
    plt.savefig(chart_path, dpi=300)
    plt.close()
    print(f"[OK] Saved recall and latency chart to: {chart_path}")

if __name__ == "__main__":
    plot_comprehensive_benchmark()
    plot_recall_and_latency()
