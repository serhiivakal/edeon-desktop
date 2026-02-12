"""
Edeon Engine — Dataset Splitters
Chemoinformatics dataset splitters: random, stratified, scaffold-aware.
"""

from collections import defaultdict


def split_dataset(X, y, smiles, mode, test_size, random_state, model_type):
    """
    Split a dataset into train/test index arrays.
    mode: 'random' | 'scaffold' | 'stratified'
    Returns (train_idx, test_idx) as lists of ints.
    """
    import numpy as np

    n = len(X)

    if mode == 'random':
        return _random_split(n, test_size, random_state)
    elif mode == 'stratified':
        return _stratified_split(y, test_size, random_state, model_type)
    elif mode == 'scaffold':
        return _scaffold_split(smiles, test_size, random_state)
    else:
        return _random_split(n, test_size, random_state)


def _random_split(n, test_size, random_state):
    import numpy as np
    rng = np.random.RandomState(random_state)
    indices = np.arange(n)
    rng.shuffle(indices)
    split_at = int(n * (1.0 - test_size))
    return indices[:split_at].tolist(), indices[split_at:].tolist()


def _stratified_split(y, test_size, random_state, model_type):
    import numpy as np

    y_arr = np.array(y)
    n = len(y_arr)

    if model_type == 'classification':
        bin_labels = y_arr.astype(int)
    else:
        try:
            percentiles = np.percentile(y_arr, [0, 20, 40, 60, 80, 100])
            edges = np.unique(percentiles)
            if len(edges) < 2:
                return _random_split(n, test_size, random_state)
            bin_labels = np.searchsorted(edges[:-1], y_arr, side='right') - 1
            bin_labels = np.clip(bin_labels, 0, len(edges) - 2)
        except Exception:
            return _random_split(n, test_size, random_state)

    rng = np.random.RandomState(random_state)
    train_idx, test_idx = [], []

    for label in np.unique(bin_labels):
        class_indices = np.where(bin_labels == label)[0]
        rng.shuffle(class_indices)
        n_test = max(1, int(len(class_indices) * test_size))
        test_idx.extend(class_indices[:n_test].tolist())
        train_idx.extend(class_indices[n_test:].tolist())

    train_arr = np.array(train_idx)
    test_arr = np.array(test_idx)
    rng.shuffle(train_arr)
    rng.shuffle(test_arr)
    return train_arr.tolist(), test_arr.tolist()


def _scaffold_split(smiles, test_size, random_state):
    import numpy as np

    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
    except ImportError:
        return _random_split(len(smiles), test_size, random_state)

    scaffold_to_indices = defaultdict(list)
    for i, smi in enumerate(smiles):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            sc = '__invalid__'
        else:
            try:
                sc = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
            except Exception:
                sc = '__invalid__'
        scaffold_to_indices[sc].append(i)

    sorted_groups = sorted(
        scaffold_to_indices.items(),
        key=lambda kv: (-len(kv[1]), kv[0])
    )

    n = len(smiles)
    n_test_target = max(1, int(n * test_size))

    test_idx, train_idx = [], []
    test_count = 0

    for sc, indices in sorted_groups:
        if test_count < n_test_target:
            test_idx.extend(indices)
            test_count += len(indices)
        else:
            train_idx.extend(indices)

    if len(train_idx) == 0:
        first_sc, first_indices = sorted_groups[0]
        first_set = set(first_indices)
        train_idx = first_indices
        test_idx = [i for i in test_idx if i not in first_set]

    return train_idx, test_idx
