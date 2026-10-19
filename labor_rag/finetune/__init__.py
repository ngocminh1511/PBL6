"""Fine-tuning data pipeline for BGE-M3 on Vietnamese labor law data.

Modules:
    generate_queries   – Synthetic query generation via Gemini Flash
    kg_pairs           – KG-based positive pairs from REFERS_TO / PART_OF
    map_vilegal_labor  – Exact ViLegalExpert -> Lao dong article mapping
    map_zaloai_labor   – Exact ZaloAI2021_LTR -> Lao dong article mapping
    mine_negatives     – Hard negative mining with pretrained bge-m3
    assemble_dataset   – Assemble train/val splits
    train              – Two-phase fine-tuning with sentence-transformers
"""
