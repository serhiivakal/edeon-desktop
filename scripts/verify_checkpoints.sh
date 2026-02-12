#!/bin/bash
# Edeon Phase 2 — Checkpoint Verification Script
# Verifies the SHA-256 hash of each checkpoint file against data/checkpoints/MANIFEST.json.

set -e

MANIFEST="data/checkpoints/MANIFEST.json"

if [ ! -f "$MANIFEST" ]; then
    echo "Error: Checkpoint manifest $MANIFEST not found."
    exit 1
fi

echo "=== Verifying Edeon Checkpoints ==="

# Parse JSON and check hashes using python
python3 -c "
import os
import json
import hashlib

def sha256sum(filename):
    h = hashlib.sha256()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(128*1024), b''):
            h.update(chunk)
    return h.hexdigest()

with open('$MANIFEST') as f:
    manifest = json.load(f)

success = True
for ep, info in manifest.items():
    print(f'Checking {ep} (version {info[\"version\"]})...')
    for filepath, expected_hash in info['artifacts'].items():
        full_path = os.path.join('data/checkpoints', filepath)
        if not os.path.exists(full_path):
            print(f'  [MISSING] {full_path}')
            success = False
            continue
            
        actual_hash = sha256sum(full_path)
        if actual_hash == expected_hash:
            print(f'  [ OK ] {filepath}')
        else:
            print(f'  [FAIL] {filepath} (Hash mismatch!)')
            print(f'    Expected: {expected_hash}')
            print(f'    Actual:   {actual_hash}')
            success = False

if success:
    print('=== All checkpoints verified successfully! ===')
    exit(0)
else:
    print('=== Checkpoint verification FAILED! ===')
    exit(1)
"
