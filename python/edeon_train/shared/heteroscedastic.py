import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

class HeteroscedasticMLP(nn.Module):
    """Multi-Layer Perceptron for heteroscedastic regression.
    
    Predicts both a mean (mu) and a log-variance (log_var) for each input.
    """
    def __init__(self, feature_dim: int, hidden_dim: int = 512, depth: int = 3, dropout: float = 0.1):
        super().__init__()
        layers = []
        in_dim = feature_dim
        for _ in range(depth):
            layers += [nn.Linear(in_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)]
            in_dim = hidden_dim
        self.shared = nn.Sequential(*layers)
        self.mean_head = nn.Linear(hidden_dim, 1)
        self.log_var_head = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        h = self.shared(x)
        mean = self.mean_head(h).squeeze(-1)
        log_var = self.log_var_head(h).squeeze(-1)
        # Clamp log_var for numerical stability
        log_var = torch.clamp(log_var, min=-10.0, max=10.0)
        return mean, log_var

def gaussian_nll_loss(mean: torch.Tensor, log_var: torch.Tensor, target: torch.Tensor, var_min: float = 1e-6) -> torch.Tensor:
    """Gaussian Negative Log-Likelihood loss function."""
    var = torch.exp(log_var).clamp(min=var_min)
    return 0.5 * (log_var + (target - mean).pow(2) / var).mean()

def train_heteroscedastic_ensemble(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    config: dict, output_dir: Path,
    seeds: List[int] = [0, 1, 2, 3, 4],
) -> Dict[str, Any]:
    """Trains K heteroscedastic MLP models with different seeds.
    
    Saves each as state_dict in output_dir/seed_{k}.pt. Returns per-seed val NLL.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    feature_dim = X_train.shape[1]
    hidden_dim = config.get("hidden_dim", 512)
    depth = config.get("depth", 3)
    dropout = config.get("dropout", 0.1)
    max_epochs = config.get("max_epochs", 200)
    lr = config.get("lr", 5e-4)
    batch_size = config.get("batch_size", 64)
    patience = config.get("patience", 15)
    
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.float32)
    X_val_t = torch.tensor(X_val, dtype=torch.float32)
    y_val_t = torch.tensor(y_val, dtype=torch.float32)
    
    train_dataset = torch.utils.data.TensorDataset(X_train_t, y_train_t)
    
    val_nlls = {}
    
    for seed in seeds:
        torch.manual_seed(seed)
        np.random.seed(seed)
        
        train_loader = torch.utils.data.DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True
        )
        
        model = HeteroscedasticMLP(feature_dim, hidden_dim, depth, dropout)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        
        best_val_nll = float("inf")
        best_state = None
        epochs_no_improve = 0
        
        for epoch in range(max_epochs):
            model.train()
            for batch_x, batch_y in train_loader:
                optimizer.zero_grad()
                mean, log_var = model(batch_x)
                loss = gaussian_nll_loss(mean, log_var, batch_y)
                loss.backward()
                optimizer.step()
                
            model.eval()
            with torch.no_grad():
                val_mean, val_log_var = model(X_val_t)
                val_loss = gaussian_nll_loss(val_mean, val_log_var, y_val_t).item()
                
            if val_loss < best_val_nll:
                best_val_nll = val_loss
                best_state = {k: v.cpu() for k, v in model.state_dict().items()}
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= patience:
                    break
                    
        # Save best model
        torch.save(best_state, output_dir / f"seed_{seed}.pt")
        val_nlls[f"seed_{seed}"] = best_val_nll
        
    return val_nlls

def predict_heteroscedastic_ensemble(
    X: np.ndarray, checkpoint_dir: Path, feature_dim: int, config: dict
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Predicts using an ensemble of heteroscedastic MLP models.
    
    Returns (mu_combined, var_combined, var_epistemic, var_aleatoric).
    """
    checkpoint_dir = Path(checkpoint_dir)
    pts = list(checkpoint_dir.glob("seed_*.pt"))
    if not pts:
        raise FileNotFoundError(f"No seed_*.pt checkpoints found in {checkpoint_dir}")
        
    hidden_dim = config.get("hidden_dim", 512)
    depth = config.get("depth", 3)
    
    X_t = torch.tensor(X, dtype=torch.float32)
    
    means = []
    vars_aleatoric = []
    
    for pt in pts:
        model = HeteroscedasticMLP(feature_dim, hidden_dim, depth, 0.0)
        model.load_state_dict(torch.load(pt))
        model.eval()
        with torch.no_grad():
            mu, log_var = model(X_t)
            means.append(mu.numpy())
            vars_aleatoric.append(np.exp(log_var.numpy()))
            
    means = np.stack(means, axis=0)  # (K, N)
    vars_aleatoric = np.stack(vars_aleatoric, axis=0)  # (K, N)
    
    # Mixture of Gaussians combination
    mu_combined = np.mean(means, axis=0)
    var_epistemic = np.var(means, axis=0)
    var_aleatoric = np.mean(vars_aleatoric, axis=0)
    var_combined = var_epistemic + var_aleatoric
    
    return mu_combined, var_combined, var_epistemic, var_aleatoric


def hpo_heteroscedastic_mlp(
    X_train: np.ndarray,
    y_train: np.ndarray,
    smiles_train: List[str],
    inchikeys: List[str],
    n_trials: int = 20,
    cv_folds: int = 3,
    random_state: int = 42
) -> Dict[str, Any]:
    """Runs Optuna HPO for HeteroscedasticMLP using grouped Scaffold CV."""
    import logging
    import optuna
    from edeon_train.shared.baselines import ScaffoldKFold
    
    logger = logging.getLogger("edeon_train.heteroscedastic")
    logger.info(f"Starting Heteroscedastic MLP HPO: {n_trials} trials, {cv_folds}-fold grouped Scaffold CV")
    
    # Filter out NaNs
    valid_mask = ~np.isnan(X_train).any(axis=1) & ~np.isnan(y_train)
    X_valid = X_train[valid_mask]
    y_valid = y_train[valid_mask]
    smiles_valid = [smiles_train[i] for i, v in enumerate(valid_mask) if v]
    inchikeys_valid = [inchikeys[i] for i, v in enumerate(valid_mask) if v]
    
    if len(X_valid) == 0:
        raise ValueError("No valid compounds for Heteroscedastic MLP HPO!")
        
    def objective(trial: optuna.Trial) -> float:
        config = {
            "hidden_dim": trial.suggest_categorical("hidden_dim", [256, 512]),
            "depth": trial.suggest_int("depth", 2, 4),
            "dropout": trial.suggest_float("dropout", 0.0, 0.2),
            "lr": trial.suggest_float("lr", 1e-4, 1e-3, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [32, 64]),
            "max_epochs": 40,
            "patience": 10
        }
        
        kf = ScaffoldKFold(n_splits=cv_folds, random_state=random_state)
        fold_scores = []
        
        for train_idx, val_idx in kf.split(X_valid, y_valid, smiles_valid, groups=inchikeys_valid):
            X_tr, y_tr = X_valid[train_idx], y_valid[train_idx]
            X_va, y_va = X_valid[val_idx], y_valid[val_idx]
            
            # Train a single MLP model
            feature_dim = X_tr.shape[1]
            model = HeteroscedasticMLP(feature_dim, config["hidden_dim"], config["depth"], config["dropout"])
            optimizer = torch.optim.Adam(model.parameters(), lr=config["lr"])
            
            X_tr_t = torch.tensor(X_tr, dtype=torch.float32)
            y_tr_t = torch.tensor(y_tr, dtype=torch.float32)
            X_va_t = torch.tensor(X_va, dtype=torch.float32)
            y_va_t = torch.tensor(y_va, dtype=torch.float32)
            
            train_dataset = torch.utils.data.TensorDataset(X_tr_t, y_tr_t)
            train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=config["batch_size"], shuffle=True)
            
            best_val_nll = float("inf")
            epochs_no_improve = 0
            
            for epoch in range(config["max_epochs"]):
                model.train()
                for batch_x, batch_y in train_loader:
                    optimizer.zero_grad()
                    mean, log_var = model(batch_x)
                    loss = gaussian_nll_loss(mean, log_var, batch_y)
                    loss.backward()
                    optimizer.step()
                    
                model.eval()
                with torch.no_grad():
                    val_mean, val_log_var = model(X_va_t)
                    val_loss = gaussian_nll_loss(val_mean, val_log_var, y_va_t).item()
                    
                if val_loss < best_val_nll:
                    best_val_nll = val_loss
                    epochs_no_improve = 0
                else:
                    epochs_no_improve += 1
                    if epochs_no_improve >= config["patience"]:
                        break
                        
            fold_scores.append(best_val_nll)
            
        return float(np.mean(fold_scores))
        
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)
    
    logger.info(f"Heteroscedastic MLP HPO completed. Best HPO CV NLL: {study.best_value:.4f}")
    return study.best_params
