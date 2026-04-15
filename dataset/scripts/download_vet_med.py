# -*- coding: utf-8 -*-
"""
VetSync - HuggingFace vet_med Dataset Downloader
=================================================
Downloads the houck2040/vet_med dataset from HuggingFace and
converts it to CSV for use in the ASTRID chatbot knowledge base.

Usage:
    pip install datasets pandas
    python dataset/scripts/download_vet_med.py

Output:
    dataset/raw/vet_med.csv
    dataset/processed/vet_med_qa.json   (Q&A pairs ready for chatbot)
"""

import os
import sys
import json

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR     = os.path.join(BASE_DIR, "raw")
PROC_DIR    = os.path.join(BASE_DIR, "processed")
OUT_CSV     = os.path.join(RAW_DIR,  "vet_med.csv")
OUT_QA      = os.path.join(PROC_DIR, "vet_med_qa.json")

os.makedirs(RAW_DIR,  exist_ok=True)
os.makedirs(PROC_DIR, exist_ok=True)


def check_dependencies():
    """Check required packages are installed."""
    missing = []
    try:
        import datasets   # noqa
    except ImportError:
        missing.append("datasets")
    try:
        import pandas     # noqa
    except ImportError:
        missing.append("pandas")

    if missing:
        print("[ERROR] Missing packages. Run:")
        print(f"  pip install {' '.join(missing)}")
        sys.exit(1)
    print("[OK] Dependencies found: datasets, pandas")


def download_and_save():
    """Download the vet_med dataset and save to CSV + Q&A JSON."""
    from datasets import load_dataset
    import pandas as pd

    print("[...] Loading houck2040/vet_med from HuggingFace...")
    print("      This may take a minute on first download.")

    try:
        dataset = load_dataset("houck2040/vet_med", trust_remote_code=True)
    except Exception as e:
        print(f"[ERROR] Failed to load dataset: {e}")
        print("        Check your internet connection or try: pip install --upgrade datasets")
        sys.exit(1)

    print(f"[OK] Dataset loaded. Splits: {list(dataset.keys())}")

    # Use 'train' split (most datasets use this)
    split_name = "train" if "train" in dataset else list(dataset.keys())[0]
    df = dataset[split_name].to_pandas()

    print(f"[OK] Split '{split_name}': {len(df)} rows")
    print(f"     Columns: {list(df.columns)}")
    print(f"     Sample row:\n{df.iloc[0].to_dict()}")

    # Save raw CSV
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"[OK] Raw CSV saved: {OUT_CSV}")

    # Extract Q&A pairs for chatbot use
    qa_pairs = extract_qa_pairs(df)
    with open(OUT_QA, "w", encoding="utf-8") as f:
        json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
    print(f"[OK] Q&A JSON saved: {OUT_QA}  ({len(qa_pairs)} pairs)")

    return df, qa_pairs


def extract_qa_pairs(df):
    """
    Extract question-answer pairs from the dataframe.
    Handles multiple possible column name patterns from HuggingFace datasets.
    """
    qa_pairs = []

    # Common column name patterns
    question_cols = ["input", "question", "instruction", "prompt", "text", "query"]
    answer_cols   = ["output", "answer", "response", "completion", "label"]

    q_col = next((c for c in question_cols if c in df.columns), None)
    a_col = next((c for c in answer_cols   if c in df.columns), None)

    if q_col and a_col:
        print(f"[OK] Using columns: question='{q_col}', answer='{a_col}'")
        for _, row in df.iterrows():
            q = str(row[q_col]).strip()
            a = str(row[a_col]).strip()
            if q and a and q != "nan" and a != "nan" and len(q) > 5:
                qa_pairs.append({"question": q, "answer": a})
    elif "text" in df.columns:
        # Some datasets use a single 'text' column with Q: / A: format
        print("[OK] Using 'text' column with Q/A parsing")
        for _, row in df.iterrows():
            text = str(row["text"])
            if "Q:" in text and "A:" in text:
                parts = text.split("A:", 1)
                q = parts[0].replace("Q:", "").strip()
                a = parts[1].strip()
                if q and a:
                    qa_pairs.append({"question": q, "answer": a})
    else:
        # Fallback: use all text content
        print("[WARN] Could not identify Q/A columns. Saving all text content.")
        for _, row in df.iterrows():
            text = " ".join(str(v) for v in row.values if str(v) != "nan")
            if len(text) > 20:
                qa_pairs.append({"question": "", "answer": text})

    return qa_pairs


def merge_into_knowledge_base(qa_pairs):
    """
    Optionally merge Q&A pairs into the main knowledge_base.json
    as searchable entries.
    """
    kb_path = os.path.join(PROC_DIR, "knowledge_base.json")
    if not os.path.exists(kb_path):
        print("[WARN] knowledge_base.json not found. Run process_datasets.py first.")
        return

    with open(kb_path, encoding="utf-8") as f:
        kb = json.load(f)

    # Add vet_med Q&A as a searchable list
    kb["vet_med_qa"] = qa_pairs[:500]  # cap at 500 to keep size manageable
    kb["metadata"]["sources"].append("HuggingFace houck2040/vet_med")
    kb["metadata"]["vet_med_pairs"] = len(qa_pairs)

    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

    print(f"[OK] Merged {len(qa_pairs[:500])} vet_med Q&A pairs into knowledge_base.json")


if __name__ == "__main__":
    print("=" * 60)
    print("  VetSync ASTRID - HuggingFace vet_med Downloader")
    print("=" * 60)

    check_dependencies()
    df, qa_pairs = download_and_save()
    merge_into_knowledge_base(qa_pairs)

    print("\n[DONE] vet_med dataset ready!")
    print(f"  Raw CSV : {OUT_CSV}")
    print(f"  Q&A JSON: {OUT_QA}")
    print("\nNext step: restart your Flask app to use the updated knowledge base.")
