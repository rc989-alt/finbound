#!/usr/bin/env python3
"""Create updated F1 dataset with replacement samples.

F1 task = 50 FinQA + 50 TAT-QA samples.

This script creates an updated F1 dataset that:
1. Takes the F1 curated FinQA samples (50)
2. Removes the 2 dataset-issue samples that are in F1 curated
3. Adds 2 replacement samples to maintain 50 FinQA samples
4. Copies TAT-QA samples unchanged (50)

The result is stored in data/curated_samples/F1_UPDATED/
"""

import json
import shutil
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from finbound.data import FinQALoader

# Dataset issue sample IDs that are in F1 curated FinQA (only 2 of original 7)
DATASET_ISSUE_IDS = [
    "PM/2015/page_127.pdf-4",       # Wrong row for average
    "PM/2015/page_85.pdf-1",        # Wrong sign in gold
]

# 2 replacement sample IDs (hard questions not in F1 curated)
REPLACEMENT_IDS = [
    "FRT/2005/page_117.pdf-1",      # Growth comparison (4 steps)
    "ALXN/2007/page_104.pdf-1",     # Average 5 items (4 steps)
]


def main():
    # Load existing F1 curated FinQA samples
    f1_finqa_path = PROJECT_ROOT / "data" / "curated_samples" / "F1" / "finqa_samples.json"
    f1_tatqa_path = PROJECT_ROOT / "data" / "curated_samples" / "F1" / "tatqa_samples.json"

    with open(f1_finqa_path) as f:
        f1_finqa = json.load(f)

    print(f"Loaded {len(f1_finqa)} F1 curated FinQA samples")

    # Get IDs in F1 curated
    f1_finqa_ids = {s['id'] for s in f1_finqa}

    # Verify issue samples are in F1 curated
    issues_in_f1 = [sid for sid in DATASET_ISSUE_IDS if sid in f1_finqa_ids]
    print(f"Dataset issue samples in F1 curated: {len(issues_in_f1)}")
    for sid in issues_in_f1:
        print(f"  - {sid}")

    # Remove issue samples
    filtered_finqa = [s for s in f1_finqa if s['id'] not in DATASET_ISSUE_IDS]
    print(f"After removing issues: {len(filtered_finqa)} FinQA samples")

    # Load FinQA dev to get replacement samples
    loader = FinQALoader(split="dev")
    all_samples = list(loader.iter_samples())
    samples_by_id = {s.id: s for s in all_samples}

    # Verify replacements don't overlap with remaining
    remaining_ids = {s['id'] for s in filtered_finqa}
    overlaps = [sid for sid in REPLACEMENT_IDS if sid in remaining_ids]
    if overlaps:
        print(f"WARNING: Overlapping replacement samples: {overlaps}")
        return

    # Add replacement samples
    for sid in REPLACEMENT_IDS:
        if sid not in samples_by_id:
            print(f"ERROR: Replacement sample not found: {sid}")
            return
        sample = samples_by_id[sid]
        filtered_finqa.append({
            "id": sample.id,
            "question": sample.question,
            "answer": sample.answer,
            "program": " ".join(sample.program),
            "issuer": sample.id.split("/")[0],
            "filename": sample.id.rsplit("-", 1)[0]
        })

    print(f"After adding replacements: {len(filtered_finqa)} FinQA samples")

    # Create output directory
    output_dir = PROJECT_ROOT / "data" / "curated_samples" / "F1_UPDATED"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save updated FinQA samples
    finqa_output = output_dir / "finqa_samples.json"
    with open(finqa_output, 'w') as f:
        json.dump(filtered_finqa, f, indent=2)
    print(f"Saved {len(filtered_finqa)} FinQA samples to {finqa_output}")

    # Copy TAT-QA samples unchanged
    tatqa_output = output_dir / "tatqa_samples.json"
    shutil.copy(f1_tatqa_path, tatqa_output)
    with open(tatqa_output) as f:
        tatqa_count = len(json.load(f))
    print(f"Copied {tatqa_count} TAT-QA samples to {tatqa_output}")

    # Summary
    print("\n" + "="*60)
    print("F1_UPDATED DATASET SUMMARY")
    print("="*60)
    print(f"FinQA samples:      {len(filtered_finqa)}")
    print(f"  - Removed issues: {len(DATASET_ISSUE_IDS)}")
    print(f"  - Added replacements: {len(REPLACEMENT_IDS)}")
    print(f"TAT-QA samples:     {tatqa_count}")
    print(f"TOTAL:              {len(filtered_finqa) + tatqa_count}")
    print("\nRemoved samples (dataset issues):")
    for sid in DATASET_ISSUE_IDS:
        print(f"  - {sid}")
    print("\nAdded samples (hard replacements):")
    for sid in REPLACEMENT_IDS:
        print(f"  + {sid}")


if __name__ == "__main__":
    main()
