import numpy as np
import pytest
from pathlib import Path
import tempfile
from edeon_train.shared.heteroscedastic import (
    HeteroscedasticMLP,
    gaussian_nll_loss,
    train_heteroscedastic_ensemble,
    predict_heteroscedastic_ensemble,
)

def test_heteroscedastic_mlp_forward():
    X = np.random.randn(10, 20)
    import torch
    X_t = torch.tensor(X, dtype=torch.float32)
    model = HeteroscedasticMLP(feature_dim=20, hidden_dim=32, depth=2)
    mean, log_var = model(X_t)
    assert mean.shape == (10,)
    assert log_var.shape == (10,)
    assert torch.all(log_var >= -10.0)
    assert torch.all(log_var <= 10.0)

def test_gaussian_nll_loss():
    import torch
    mean = torch.tensor([0.0, 0.0])
    log_var = torch.tensor([0.0, 0.0])  # var = 1.0
    target = torch.tensor([1.0, -1.0])
    loss = gaussian_nll_loss(mean, log_var, target)
    # 0.5 * (0.0 + (1.0 - 0.0)^2 / 1.0) = 0.5
    # 0.5 * (0.0 + (-1.0 - 0.0)^2 / 1.0) = 0.5
    # mean = 0.5
    assert abs(loss.item() - 0.5) < 1e-5

def test_train_and_predict_heteroscedastic_ensemble():
    # Create synthetic linear data with heteroscedastic noise
    np.random.seed(42)
    X_train = np.random.randn(100, 10)
    # Noise increases with first feature
    noise_std = 0.1 + 0.5 * np.abs(X_train[:, 0])
    y_train = 2.0 * X_train[:, 0] + np.random.normal(0, noise_std)
    
    X_val = np.random.randn(20, 10)
    noise_std_val = 0.1 + 0.5 * np.abs(X_val[:, 0])
    y_val = 2.0 * X_val[:, 0] + np.random.normal(0, noise_std_val)
    
    config = {
        "hidden_dim": 16,
        "depth": 2,
        "max_epochs": 10,
        "lr": 1e-3,
        "batch_size": 32,
        "patience": 5
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        val_nlls = train_heteroscedastic_ensemble(
            X_train, y_train, X_val, y_val, config, tmpdir_path, seeds=[0, 1]
        )
        
        assert "seed_0" in val_nlls
        assert "seed_1" in val_nlls
        
        mu_comb, var_comb, var_ep, var_al = predict_heteroscedastic_ensemble(
            X_val, tmpdir_path, feature_dim=10, config=config
        )
        
        assert mu_comb.shape == (20,)
        assert var_comb.shape == (20,)
        assert var_ep.shape == (20,)
        assert var_al.shape == (20,)
        assert np.all(var_comb > 0)
        assert np.all(var_al > 0)
        assert np.all(var_ep >= 0)
