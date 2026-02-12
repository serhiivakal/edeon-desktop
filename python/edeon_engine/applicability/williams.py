"""
Williams Plot applicability domain visualization mapping leverage vs standardized residuals.
"""

from .__init__ import ApplicabilityDomain

def williams_plot_data(ad: ApplicabilityDomain, leverage_scores: dict) -> dict:
    """Format and map leverage vs. standardized residuals for Williams Plot.
    
    If leverage scores or residual scores are not available, returns available: False.
    """
    if not leverage_scores.get("available"):
        return {"available": False}
        
    # Standardized residuals are required for Williams Plot points
    if "std_residual" not in leverage_scores or "status" not in leverage_scores:
        return {"available": False}
        
    return {
        "available": True,
        "points": [
            {
                "leverage": float(h),
                "std_residual": float(r),
                "status": str(s)
            }
            for h, r, s in zip(leverage_scores["leverage"],
                              leverage_scores["std_residual"],
                              leverage_scores["status"])
        ],
        "h_star": float(leverage_scores["h_star"]),
        "residual_threshold": 3.0,
    }
