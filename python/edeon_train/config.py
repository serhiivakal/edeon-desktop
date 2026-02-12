"""Shared training configurations and endpoint mappings for Edeon Phase 2.

Defines the parameters, datasets, and target column metadata for all 7
Tier-1 ecotoxicity endpoints.
"""

import os
from typing import Dict, Any, List

# Central mapping from training package identifier to the Endpoint enum and Curated path
ENDPOINT_CONFIGS = {
    "bee_acute_oral_ld50": {
        "endpoint_id": "bee_acute_oral_ld50",
        "phase1_dataset": "data/curated/bee_acute_oral_ld50/v1.0",
        "target_column": "value_class",
        "target_kind": "classification",
        "primary_split": "scaffold",
        "classification": {
            "label_source": "value_class",
            "positive_label": "toxic",
            "negative_label": "nontoxic",
        },
        "performance_targets": {
            "balanced_accuracy": 0.70,
            "auc_roc": 0.75,
            "f1": 0.60,
            "ece": 0.10,
            "ad_coverage_test": 0.60
        },
        "chemprop": {
            "epochs": 50,
            "batch_size": 50,
            "depth": 3,
            "hidden_size": 300,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 300,
            "dropout": 0.0,
            "hpo_trials": 20
        }
    },
    "bee_acute_contact_ld50": {
        "endpoint_id": "bee_acute_contact_ld50",
        "phase1_dataset": "data/curated/bee_acute_contact_ld50/v1.0",
        "target_column": "value_class",
        "target_kind": "classification",
        "primary_split": "scaffold",
        "classification": {
            "label_source": "value_class",
            "positive_label": "toxic",
            "negative_label": "nontoxic",
        },
        "performance_targets": {
            "balanced_accuracy": 0.70,
            "auc_roc": 0.75,
            "f1": 0.60,
            "ece": 0.10,
            "ad_coverage_test": 0.60
        },
        "chemprop": {
            "epochs": 50,
            "batch_size": 50,
            "depth": 3,
            "hidden_size": 300,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 300,
            "dropout": 0.0,
            "hpo_trials": 20
        }
    },
    "fish_acute_lc50": {
        "endpoint_id": "fish_acute_lc50",
        "phase1_dataset": "data/curated/fish_acute_lc50/v1.0",
        "target_column": "value",
        "target_kind": "classification",
        "primary_split": "scaffold",
        "classification": {
            "label_source": "threshold",
            "threshold_column": "value",
            "threshold_value": 10.0,
            "threshold_direction": "le",
            "positive_label": "toxic",
            "negative_label": "nontoxic",
        },
        "performance_targets": {
            "balanced_accuracy": 0.70,
            "auc_roc": 0.75,
            "f1": 0.60,
            "ece": 0.10,
            "ad_coverage_test": 0.60
        },
        "chemprop": {
            "epochs": 50,
            "batch_size": 64,
            "depth": 3,
            "hidden_size": 300,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 300,
            "dropout": 0.1,
            "hpo_trials": 20
        }
    },
    "daphnia_acute_ec50": {
        "endpoint_id": "daphnia_acute_ec50",
        "phase1_dataset": "data/curated/daphnia_acute_ec50/v1.0",
        "target_column": "value_log",
        "target_kind": "regression",
        "primary_split": "scaffold",
        "performance_targets": {
            "rmse_log": 0.65,
            "r2": 0.65,
            "ad_coverage_test": 0.60
        },
        "chemprop": {
            "epochs": 50,
            "batch_size": 50,
            "depth": 3,
            "hidden_size": 300,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 300,
            "dropout": 0.0,
            "hpo_trials": 20
        }
    },
    "algae_growth_ec50": {
        "endpoint_id": "algae_growth_ec50",
        "phase1_dataset": "data/curated/algae_growth_ec50/v1.0",
        "target_column": "value",
        "target_kind": "classification",
        "primary_split": "scaffold",
        "classification": {
            "label_source": "threshold",
            "threshold_column": "value",
            "threshold_value": 1.0,
            "threshold_direction": "le",
            "positive_label": "toxic",
            "negative_label": "nontoxic",
        },
        "performance_targets": {
            "balanced_accuracy": 0.65,
            "auc_roc": 0.70,
            "f1": 0.55,
            "ece": 0.15,
            "ad_coverage_test": 0.50
        },
        "chemprop": {
            "epochs": 40,
            "batch_size": 32,
            "depth": 2,
            "hidden_size": 150,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 150,
            "dropout": 0.1,
            "hpo_trials": 15
        }
    },
    "earthworm_acute_lc50": {
        "endpoint_id": "earthworm_acute_lc50",
        "phase1_dataset": "data/curated/earthworm_acute_lc50/v1.0",
        "target_column": "value_log",
        "target_kind": "regression",
        "primary_split": "scaffold",
        "performance_targets": {
            "rmse_log": 0.70,
            "r2": 0.60,
            "ad_coverage_test": 0.50
        },
        "chemprop": {
            "epochs": 40,
            "batch_size": 32,
            "depth": 2,
            "hidden_size": 150,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 150,
            "dropout": 0.1,
            "hpo_trials": 15
        }
    },
    "bird_acute_oral_ld50": {
        "endpoint_id": "bird_acute_oral_ld50",
        "phase1_dataset": "data/curated/bird_acute_oral_ld50/v1.0",
        "target_column": "value",
        "target_kind": "classification",
        "primary_split": "scaffold",
        "classification": {
            "label_source": "threshold",
            "threshold_column": "value",
            "threshold_value": 2000.0,
            "threshold_direction": "le",
            "positive_label": "toxic",
            "negative_label": "nontoxic",
        },
        "performance_targets": {
            "balanced_accuracy": 0.65,
            "auc_roc": 0.70,
            "f1": 0.55,
            "ece": 0.15,
            "ad_coverage_test": 0.40
        },
        "chemprop": {
            "epochs": 30,
            "batch_size": 16,
            "depth": 2,
            "hidden_size": 150,
            "ffn_num_layers": 1,
            "ffn_hidden_size": 150,
            "dropout": 0.2,
            "hpo_trials": 10
        }
    },
    "soil_koc": {
        "endpoint_id": "soil_koc",
        "phase1_dataset": "data/curated/soil_koc/v1.0",
        "target_column": "value_log",
        "target_kind": "regression",
        "primary_split": "scaffold",
        "performance_targets": {
            "rmse_log": 0.50,
            "r2": 0.75,
            "ad_coverage_test": 0.60
        },
        "chemprop": {
            "epochs": 50,
            "batch_size": 50,
            "depth": 3,
            "hidden_size": 300,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 300,
            "dropout": 0.0,
            "hpo_trials": 20
        }
    },
    "soil_dt50": {
        "endpoint_id": "soil_dt50",
        "phase1_dataset": "data/curated/soil_dt50/v1.0",
        "target_column": "value_log",
        "target_kind": "regression_heteroscedastic",
        "primary_split": "scaffold",
        "performance_targets": {
            "nll_log10": 1.5,
            "coverage_95": 0.95,
            "ad_coverage_test": 0.50
        },
        "chemprop": {
            "epochs": 80,
            "batch_size": 64,
            "depth": 3,
            "hidden_size": 300,
            "ffn_num_layers": 2,
            "ffn_hidden_size": 300,
            "dropout": 0.1,
            "hpo_trials": 20
        }
    }
}
