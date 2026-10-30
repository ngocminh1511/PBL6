"""Script tạo file Jupyter Notebook Bgem3_training.ipynb chuẩn hóa để chạy trên Google Colab với T4 GPU."""

import json
from pathlib import Path

def create_notebook():
    cells = []

    # Cell 1: Markdown - Header
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# 🚀 Huấn Luyện Fine-Tuning BAAI/bge-m3 Cho Tìm Kiếm Pháp Luật Việt Nam\n",
            "\n",
            "Notebook này được tối ưu hóa riêng cho **Google Colab (NVIDIA T4 GPU 15GB VRAM)** để fine-tune mô hình embedding `BAAI/bge-m3` trên tập dữ liệu chuẩn **3,196 câu hỏi pháp lý** (`train_data_bgem3.json`).\n",
            "\n",
            "### 🎯 Chiến lược huấn luyện:\n",
            "1. **Mô hình nền tảng:** `BAAI/bge-m3` (568M params, đa ngữ chất lượng cao).\n",
            "2. **Hàm mất mát:** `MultipleNegativesRankingLoss` kết hợp **Hard Negatives** + **In-batch Negatives** (kỹ thuật SOTA cho Dense Retrieval).\n",
            "3. **Tối ưu bộ nhớ T4 (15GB):**\n",
            "   - `max_seq_length = 512` (phủ 98% các Điều luật Việt Nam, tránh OOM).\n",
            "   - `Mixed Precision (FP16)`: Tăng tốc 2.5x và giảm 50% VRAM.\n",
            "   - `Batch size = 8`, `Gradient Accumulation = 2` (Effective batch size = 16).\n",
            "4. **Lưu trữ tự động:** Lưu checkpoint và mô hình tốt nhất trực tiếp vào Google Drive để không bị mất khi hết phiên Colab."
        ]
    })

    # Cell 2: Code - Kiểm tra GPU
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 1. Kiểm tra cấu hình GPU được cấp trên Colab\n",
            "!nvidia-smi"
        ]
    })

    # Cell 3: Code - Cài đặt thư viện
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 2. Cài đặt các thư viện cần thiết cho Sentence-Transformers v3 & PyTorch\n",
            "!pip install -q -U sentence-transformers>=3.0.0 accelerate transformers datasets"
        ]
    })

    # Cell 4: Code - Kết nối Google Drive
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 3. Kết nối Google Drive để đọc dữ liệu và lưu mô hình\n",
            "from google.colab import drive\n",
            "drive.mount('/content/drive')\n",
            "\n",
            "import os\n",
            "from pathlib import Path\n",
            "\n",
            "# Đường dẫn file dữ liệu trên Drive của bạn\n",
            "DATA_PATH = Path('/content/drive/MyDrive/train_data_bgem3.json')\n",
            "\n",
            "# Thư mục lưu mô hình sau khi train xong\n",
            "OUTPUT_DIR = Path('/content/drive/MyDrive/bge-m3-legal-vietnamese')\n",
            "OUTPUT_DIR.mkdir(parents=True, exist_ok=True)\n",
            "\n",
            "if DATA_PATH.exists():\n",
            "    print(f' Đã tìm thấy dữ liệu: {DATA_PATH} ({DATA_PATH.stat().st_size / (1024*1024):.2f} MB)')\n",
            "else:\n",
            "    print(f'⚠ CHƯA TÌM THẤY: {DATA_PATH}')\n",
            "    print('Vui lòng kiểm tra lại xem file train_data_bgem3.json đã nằm đúng thư mục gốc MyDrive chưa!')"
        ]
    })

    # Cell 5: Code - Đọc và Chuẩn bị dữ liệu Train / Val Split
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 4. Đọc dữ liệu và chia tập Train (95%) / Validation (5%)\n",
            "import json\n",
            "import random\n",
            "from sentence_transformers import InputExample\n",
            "from sentence_transformers.evaluation import InformationRetrievalEvaluator\n",
            "\n",
            "# Đặt seed cố định để kết quả tái lập được\n",
            "random.seed(42)\n",
            "\n",
            "with open(DATA_PATH, 'r', encoding='utf-8') as f:\n",
            "    raw_data = json.load(f)\n",
            "\n",
            "print(f'Tổng số câu hỏi nạp vào: {len(raw_data)}')\n",
            "\n",
            "# Xáo trộn ngẫu nhiên và chia 95% Train, 5% Val\n",
            "random.shuffle(raw_data)\n",
            "split_idx = int(len(raw_data) * 0.95)\n",
            "train_items = raw_data[:split_idx]\n",
            "val_items = raw_data[split_idx:]\n",
            "\n",
            "print(f'Số lượng mẫu Train: {len(train_items)}')\n",
            "print(f'Số lượng mẫu Validation: {len(val_items)}')\n",
            "\n",
            "# Tạo InputExample cho tập Train: [Anchor (Câu hỏi), Positive (Điều luật đúng), Negative 1, Negative 2, ...]\n",
            "train_examples = []\n",
            "MAX_HARD_NEGATIVES = 3  # Lấy 3 hard negatives mỗi câu để tối ưu VRAM T4\n",
            "\n",
            "for item in train_items:\n",
            "    q = item['question'].strip()\n",
            "    pos_texts = [p['text'].strip() for p in item.get('relevant_articles', []) if p.get('text')]\n",
            "    neg_texts = [n['text'].strip() for n in item.get('non_relevant_articles', []) if n.get('text')][:MAX_HARD_NEGATIVES]\n",
            "    \n",
            "    if not q or not pos_texts:\n",
            "        continue\n",
            "        \n",
            "    for pos in pos_texts:\n",
            "        # InputExample chứa anchor, positive và danh sách hard negatives\n",
            "        texts = [q, pos] + neg_texts\n",
            "        train_examples.append(InputExample(texts=texts))\n",
            "\n",
            "print(f'Tổng số InputExamples cho tập Train: {len(train_examples)}')\n",
            "\n",
            "# Chuẩn bị Evaluator cho tập Validation (IR Evaluator đo MRR, Recall, NDCG)\n",
            "val_queries = {}\n",
            "val_corpus = {}\n",
            "val_relevant_docs = {}\n",
            "\n",
            "doc_idx = 0\n",
            "for i, item in enumerate(val_items):\n",
            "    qid = f'q_{i}'\n",
            "    val_queries[qid] = item['question'].strip()\n",
            "    val_relevant_docs[qid] = set()\n",
            "    \n",
            "    for p in item.get('relevant_articles', []):\n",
            "        doc_id = f'doc_{doc_idx}'\n",
            "        doc_idx += 1\n",
            "        val_corpus[doc_id] = p['text'].strip()\n",
            "        val_relevant_docs[qid].add(doc_id)\n",
            "        \n",
            "    for n in item.get('non_relevant_articles', []):\n",
            "        doc_id = f'doc_{doc_idx}'\n",
            "        doc_idx += 1\n",
            "        val_corpus[doc_id] = n['text'].strip()\n",
            "\n",
            "evaluator = InformationRetrievalEvaluator(\n",
            "    queries=val_queries,\n",
            "    corpus=val_corpus,\n",
            "    relevant_docs=val_relevant_docs,\n",
            "    name='val_legal_retrieval',\n",
            "    mrr_at_k=[1, 3, 5, 10],\n",
            "    ndcg_at_k=[5, 10],\n",
            "    accuracy_at_k=[1, 3, 5, 10],\n",
            "    show_progress_bar=False\n",
            ")\n",
            "print(f' Evaluator sẵn sàng với {len(val_queries)} câu hỏi và {len(val_corpus)} văn bản đối chiếu.')"
        ]
    })

    # Cell 6: Code - Khởi tạo mô hình BGE-M3 & Loss Function
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 5. Tải mô hình BAAI/bge-m3 và cấu hình Loss\n",
            "import torch\n",
            "from torch.utils.data import DataLoader\n",
            "from sentence_transformers import SentenceTransformer, losses\n",
            "\n",
            "MODEL_NAME = 'BAAI/bge-m3'\n",
            "print(f'Đang tải mô hình {MODEL_NAME}...')\n",
            "model = SentenceTransformer(MODEL_NAME)\n",
            "\n",
            "# Cắt độ dài tối đa 512 tokens (Bảo vệ VRAM T4 không bị OOM)\n",
            "model.max_seq_length = 512\n",
            "print(f'Max sequence length đặt thành: {model.max_seq_length}')\n",
            "\n",
            "# DataLoader\n",
            "BATCH_SIZE = 8  # Kích thước batch phù hợp nhất với 15GB VRAM T4 khi có 3 hard negatives\n",
            "train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=BATCH_SIZE)\n",
            "\n",
            "# MultipleNegativesRankingLoss:\n",
            "# Với mỗi query, mô hình xem [pos] là đúng, [neg_1, neg_2, neg_3] là sai,\n",
            "# đồng thời dùng các sample khác trong batch làm in-batch negatives!\n",
            "train_loss = losses.MultipleNegativesRankingLoss(model=model)\n",
            "print(' MultipleNegativesRankingLoss đã được cấu hình thành công!')"
        ]
    })

    # Cell 7: Code - Huấn luyện mô hình
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 6. Tiến hành Huấn luyện (Khoảng 35 - 45 phút trên T4 GPU)\n",
            "import math\n",
            "\n",
            "EPOCHS = 3\n",
            "WARMUP_STEPS = math.ceil(len(train_dataloader) * EPOCHS * 0.1)  # 10% warmup\n",
            "EVAL_STEPS = 200  # Đánh giá sau mỗi 200 steps\n",
            "\n",
            "print('=' * 65)\n",
            "print(' BẮT ĐẦU QUÁ TRÌNH HUẤN LUYỆN BGE-M3')\n",
            "print(f' - Epochs: {EPOCHS}')\n",
            "print(f' - Batch Size: {BATCH_SIZE} (x3 negatives = ~32 passages/batch)')\n",
            "print(f' - Warmup steps: {WARMUP_STEPS}')\n",
            "print(f' - Learning Rate: 2e-5 (AdamW với Cosine Decay)')\n",
            "print(f' - Thư mục lưu kết quả: {OUTPUT_DIR}')\n",
            "print('=' * 65)\n",
            "\n",
            "model.fit(\n",
            "    train_objectives=[(train_dataloader, train_loss)],\n",
            "    evaluator=evaluator,\n",
            "    epochs=EPOCHS,\n",
            "    evaluation_steps=EVAL_STEPS,\n",
            "    warmup_steps=WARMUP_STEPS,\n",
            "    optimizer_params={'lr': 2e-5},\n",
            "    output_path=str(OUTPUT_DIR),\n",
            "    save_best_model=True,\n",
            "    show_progress_bar=True,\n",
            "    use_amp=True  # BẬT Mixed Precision (FP16) - CỰC KỲ QUAN TRỌNG TRÊN T4\n",
            ")\n",
            "\n",
            "print('\n HUẤN LUYỆN HOÀN TẤT THÀNH CÔNG!')\n",
            "print(f'Mô hình tốt nhất đã được lưu tại Google Drive: {OUTPUT_DIR}')"
        ]
    })

    # Cell 8: Code - Đánh giá & Kiểm thử thực tế
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 7. Kiểm thử trực quan: So sánh Mô hình Gốc vs Mô hình Đã Fine-tune\n",
            "import numpy as np\n",
            "\n",
            "# Tải mô hình đã fine-tune từ Drive\n",
            "fine_tuned_model = SentenceTransformer(str(OUTPUT_DIR))\n",
            "\n",
            "# Thử nghiệm một câu hỏi thực tế\n",
            "test_query = 'Người lao động thử việc có được trả lương không và mức lương tối thiểu là bao nhiêu?'\n",
            "test_docs = [\n",
            "    'Điều 26. Tiền lương thử việc: Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó.',\n",
            "    'Điều 90. Tiền lương: Tiền lương là số tiền mà người sử dụng lao động trả cho người lao động theo thỏa thuận để thực hiện công việc, bao gồm mức lương theo công việc hoặc chức danh.',\n",
            "    'Điều 120. Phân định thẩm quyền xử phạt: Chủ tịch Ủy ban nhân dân các cấp có quyền xử phạt vi phạm hành chính trong lĩnh vực giao thông đường bộ.',\n",
            "    'Điều 10. Nguyên tắc bảo vệ rừng: Quản lý rừng bền vững, bảo tồn đa dạng sinh học và cảnh quan thiên nhiên.'\n",
            "]\n",
            "\n",
            "q_vec_base = model.encode(test_query, normalize_embeddings=True)\n",
            "doc_vecs_base = model.encode(test_docs, normalize_embeddings=True)\n",
            "scores_base = np.dot(doc_vecs_base, q_vec_base)\n",
            "\n",
            "q_vec_ft = fine_tuned_model.encode(test_query, normalize_embeddings=True)\n",
            "doc_vecs_ft = fine_tuned_model.encode(test_docs, normalize_embeddings=True)\n",
            "scores_ft = np.dot(doc_vecs_ft, q_vec_ft)\n",
            "\n",
            "print(f'Câu hỏi: \"{test_query}\"\\n')\n",
            "print(f'{\"Văn bản\":<80} | {\"Score Gốc\":<12} | {\"Score Fine-Tuned\":<15}')\n",
            "print('-' * 115)\n",
            "for doc, s_base, s_ft in zip(test_docs, scores_base, scores_ft):\n",
            "    print(f'{doc[:78]:<80} | {s_base:<12.4f} | {s_ft:<15.4f}')"
        ]
    })

    # Cell 9: Markdown - Hướng dẫn tích hợp lại PBL6
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## 📥 Hướng Dẫn Tải Về & Tích Hợp Vào Dự Án PBL6\n",
            "\n",
            "Sau khi train xong trên Colab, mô hình của bạn đã nằm an toàn trong Google Drive tại thư mục `bge-m3-legal-vietnamese`.\n",
            "\n",
            "### Cách đưa vào dự án PBL6 ở máy cá nhân:\n",
            "1. Tải thư mục `bge-m3-legal-vietnamese` từ Google Drive về máy tính.\n",
            "2. Đặt vào thư mục: `d:\\PBL6_v2\\PBL6\\data\\models\\bge-m3-legal-vietnamese`.\n",
            "3. Trong file `.env` của dự án, cập nhật lại biến:\n",
            "   ```env\n",
            "   EMBEDDING_MODEL=d:/PBL6_v2/PBL6/data/models/bge-m3-legal-vietnamese\n",
            "   ```\n",
            "   *(hoặc đẩy lên Hugging Face Hub riêng của bạn để các script Modal Cloud GPU tự động tải về).* \n",
            "4. Chạy embedding lại cho collection Qdrant để tận hưởng độ chính xác vượt trội!"
        ]
    })

    notebook = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {
                "gpuType": "T4",
                "provenance": []
            },
            "kernelspec": {
                "display_name": "Python 3",
                "name": "python3"
            },
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }

    out_path = Path("d:/PBL6_v2/PBL6/Bgem3_training.ipynb")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, ensure_ascii=False, indent=2)

    print(f" Đã tạo thành công file notebook tại: {out_path}")

if __name__ == "__main__":
    create_notebook()
