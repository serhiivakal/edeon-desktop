import sys
sys.path.insert(0, '/home/svakal/Projects/Edeon/python')

from edeon_engine.models.trainers import train_model_batch

# Define dummy data (15 compounds to satisfy the minimum requirements of 10 curated and 5 split)
smiles_list = [
    "CCO", "CC(=O)O", "CCC", "CCCC", "CO", "CCO", "CC(=O)O", "CCC", "CCCC", "CO",
    "CCO", "CC(=O)O", "CCC", "CCCC", "CO", "CCO", "CC(=O)O", "CCC", "CCCC", "CO",
]
# Make sure we have 20 unique-ish SMILES or curated SMILES
smiles_list = [
    "C", "CC", "CCC", "CCCC", "CCCCC", "CCCCCC", "CCCCCCC", "CCCCCCCC", "CCCCCCCCC", "CCCCCCCCCC",
    "CCO", "CC(=O)O", "CNC", "C(=O)O", "CS", "C1CCCCC1", "c1ccccc1", "c1ccccc1O", "c1ccccc1Cl", "c1ccccc1F"
]

activities = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0, 3.2, 1.1, 1.3, 1.4, 0.9, 1.0, 1.8, 2.1, 2.2, 2.4, 2.3]

config = {
    "model_type": "regression",
    "algorithm": "Random Forest",
    "featurizer_selections": [
        {
            "id": "descriptors_2d",
            "params": {"selected": ["MW", "LogP", "TPSA", "HBD", "HBA", "RotBonds"]}
        }
    ],
    "hyperparameters": {
        "n_estimators": 10
    },
    "split_mode": "random",
    "test_size": 0.2,
    "random_seed": 42,
    "cv_folds": 3,
    "n_scramble": 0
}

try:
    print("Starting training...")
    result = train_model_batch(smiles_list, activities, config)
    print("SUCCESS! Metrics:")
    print(result["metrics"])
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
