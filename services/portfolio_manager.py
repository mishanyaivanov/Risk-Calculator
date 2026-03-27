import numpy as np
from scipy.stats import norm
from typing import List, Dict, Tuple

def calculate_portfolio_var(
    returns: np.ndarray, 
    weights: np.ndarray, 
    confidence: float = 0.95, 
    portfolio_value: float = 1.0
) -> Dict:
    """
    Calculates Parametric VaR for a portfolio using the Variance-Covariance method.
    """
    if returns.shape[1] != len(weights):
        raise ValueError("Number of assets in returns and weights must match.")
        
    cov_matrix = np.cov(returns, rowvar=False)
    
    if returns.shape[1] == 1:
        port_variance = cov_matrix
        port_std = np.sqrt(port_variance)
    else:
        port_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
        port_std = np.sqrt(port_variance)
    
    z_score = norm.ppf(confidence)
    var_value = portfolio_value * z_score * port_std
    
    annual_return = np.sum(np.mean(returns, axis=0) * weights) * 252
    annual_volatility = port_std * np.sqrt(252)

    return {
        "var_value": var_value,
        "portfolio_std": port_std,
        "z_score": z_score,
        "covariance_matrix": cov_matrix.tolist() if hasattr(cov_matrix, 'tolist') else cov_matrix,
        "annual_return": annual_return,
        "annual_volatility": annual_volatility
    }

def generate_efficient_frontier(
    returns: np.ndarray, 
    num_portfolios: int = 1000
) -> Dict:
    """
    Generates random portfolios to visualize the Efficient Frontier.
    """
    num_assets = returns.shape[1]
    mean_returns = np.mean(returns, axis=0)
    cov_matrix = np.cov(returns, rowvar=False)
    
    results = np.zeros((3, num_portfolios))
    
    for i in range(num_portfolios):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)
        
        portfolio_return = np.sum(mean_returns * weights) * 252
        portfolio_std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
        
        results[0,i] = portfolio_std_dev
        results[1,i] = portfolio_return
        results[2,i] = results[1,i] / results[0,i] if results[0,i] > 0 else 0
        
    return {
        "volatility": results[0].tolist(),
        "returns": results[1].tolist(),
        "sharpe": results[2].tolist()
    }
