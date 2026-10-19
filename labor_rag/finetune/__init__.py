"""Fine-tuning data pipeline for BGE-M3 on Vietnamese labor law data.

Modules:
    generate_queries   – Synthetic query generation via Gemini Flash
    kg_pairs           – KG-based positive pairs from REFERS_TO / PART_OF
    mine_negatives     – Hard negative mining with pretrained bge-m3
    assemble_dataset   – Assemble train/val splits
    train              – Two-phase fine-tuning with sentence-transformers
"""

