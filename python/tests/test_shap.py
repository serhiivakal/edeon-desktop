import unittest
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from edeon_engine.interpret.shap_explainer import explain_model, standardised_coefficients

class TestSHAP(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        
    def test_tree_shap_on_100_row_rf_expected_shape(self):
        # 1. TreeSHAP on a 100-row RF returns SHAP array of expected shape.
        X = np.random.normal(size=(100, 4))
        y = X[:, 0] * 3.0 + X[:, 1] * 1.5 + np.random.normal(size=100) * 0.1
        
        rf = RandomForestRegressor(n_estimators=5, random_state=42)
        rf.fit(X, y)
        
        feature_names = ["F1", "F2", "F3", "F4"]
        explanation = explain_model(
            estimator=rf,
            algorithm="rf",
            model_type="regression",
            X_train=X,
            X_eval=X,
            feature_names=feature_names
        )
        
        shap_values = np.array(explanation["shap_values"])
        self.assertEqual(shap_values.shape, (100, 4))

    def test_shap_global_and_gini_directional_agreement(self):
        # 2. SHAP global importance and Gini agree directionally on top-3 features for synthetic linear data.
        X = np.random.normal(size=(150, 6))
        # Top 3 features are F0, F1, F2; others are noise
        y = X[:, 0] * 10.0 + X[:, 1] * 6.0 + X[:, 2] * 4.0 + np.random.normal(size=150) * 0.1
        
        rf = RandomForestRegressor(n_estimators=10, random_state=42)
        rf.fit(X, y)
        
        feature_names = [f"F{i}" for i in range(6)]
        explanation = explain_model(
            estimator=rf,
            algorithm="rf",
            model_type="regression",
            X_train=X,
            X_eval=X,
            feature_names=feature_names
        )
        
        # Get top-3 features from Gini (Random Forest)
        gini_importances = rf.feature_importances_
        gini_top_3_indices = np.argsort(gini_importances)[::-1][:3]
        gini_top_3_names = {feature_names[i] for i in gini_top_3_indices}
        
        # Get top-3 features from SHAP global importance
        shap_global = explanation["global_importance"]
        shap_top_3_names = {item["name"] for item in shap_global[:3]}
        
        # Expect F0, F1, F2 in both
        expected_top_3 = {"F0", "F1", "F2"}
        self.assertEqual(gini_top_3_names, expected_top_3)
        self.assertEqual(shap_top_3_names, expected_top_3)

    def test_linear_shap_and_std_coefficients_agreement(self):
        # 3. LinearSHAP and standardised coefficients agree to within 1 % on a Ridge model.
        X = np.random.normal(size=(100, 5))
        y = X[:, 0] * 2.5 - X[:, 1] * 1.8 + X[:, 2] * 0.9 + np.random.normal(size=100) * 0.1
        
        # Standardize X explicitly to ensure exact mathematical standard deviation scale
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        model = Ridge(alpha=1.0)
        model.fit(X_scaled, y)
        
        feature_names = [f"F{i}" for i in range(5)]
        explanation = explain_model(
            estimator=model,
            algorithm="ridge",
            model_type="regression",
            X_train=X_scaled,
            X_eval=X_scaled,
            feature_names=feature_names
        )
        
        # Extract SHAP standard deviations
        shap_values = np.array(explanation["shap_values"])
        shap_std = np.std(shap_values, axis=0)
        
        # Extract standardized coefficients
        linear_coefs = {item["name"]: item["std_coef"] for item in explanation["linear_coefficients"]}
        
        # Compare SHAP std with abs(std_coef) for each feature
        for i, name in enumerate(feature_names):
            std_coef = linear_coefs[name]
            # Ridge LinearSHAP uses background reference. On scaled data:
            # SHAP_j = std_coef_j * (x_j - mean_j)
            # std(SHAP_j) should be exactly equal to abs(std_coef_j) * std(x_j) = abs(std_coef_j) * 1.0 = abs(std_coef_j)
            # Due to background sampling size, there might be a tiny variance of < 1%
            self.assertAlmostEqual(shap_std[i], abs(std_coef), delta=abs(std_coef) * 0.01)

if __name__ == "__main__":
    unittest.main()
