import math
import numpy as np
from scipy.stats import norm
from typing import List, Dict

def covariance_from_sigmas_and_correlation(
    sigma_values: List[float],
    correlation_matrix: List[List[float]],
) -> List[List[float]]:
    """
    Calculates a covariance matrix from standard deviations and a correlation matrix.
    """
    n = len(sigma_values)
    if len(correlation_matrix) != n or any(len(row) != n for row in correlation_matrix):
        raise ValueError("Correlation matrix must be square and match the number of sigma values.")

    cov_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            cov_matrix[i, j] = sigma_values[i] * sigma_values[j] * correlation_matrix[i][j]
    return cov_matrix.tolist()

def option_var_moment_approximations(
    delta_cash: float,
    gamma_cash: float,
    theta_horizon: float,
    mu_horizon: float,
    sigma_horizon: float,
    z_value: float,
) -> Dict[str, float]:
    """
    Calculates Delta-Normal and Delta-Gamma VaR approximations.
    """
    # Delta-Normal VaR
    mu_dn = delta_cash * mu_horizon + theta_horizon
    sigma_dn = abs(delta_cash) * sigma_horizon
    q_dn = mu_dn - z_value * sigma_dn
    var_dn = max(0.0, -q_dn)

    # Delta-Gamma VaR (moment matching approximation)
    # PnL = delta_cash * dS + 0.5 * gamma_cash * dS^2 + theta_horizon
    # dS = S_0 * (exp(mu_horizon + sigma_horizon * Z) - 1)
    # For simplicity, we assume dS is normally distributed with mean mu_horizon and std sigma_horizon
    # This is a simplification, a more rigorous approach would use moments of dS
    # Here, we use the moments of the PnL distribution directly
    
    # Expected value of PnL
    mu_pnl = delta_cash * mu_horizon + 0.5 * gamma_cash * (sigma_horizon**2 + mu_horizon**2) + theta_horizon
    
    # Variance of PnL (simplified for illustration, a full derivation is complex)
    # Var(PnL) approx = (delta_cash^2 * sigma_dS^2) + (0.5 * gamma_cash * sigma_dS^2)^2 * 2
    # Using moments of chi-squared for gamma term
    
    # A common approximation for Delta-Gamma variance is:
    # Var(PnL) = (delta_cash * sigma_horizon)^2 + 0.5 * (gamma_cash * sigma_horizon^2)^2
    # This is still an approximation. For a more accurate one, one would need to use higher moments.
    # For this implementation, let's use a simpler, but common approximation for the variance:
    sigma_pnl_squared = (delta_cash * sigma_horizon)**2 + 0.5 * (gamma_cash * sigma_horizon**2)**2
    sigma_dg = math.sqrt(max(0.0, sigma_pnl_squared))

    q_dg = mu_pnl - z_value * sigma_dg
    var_dg = max(0.0, -q_dg)

    return {
        "mu_dn": mu_dn, "sigma_dn": sigma_dn, "q_dn": q_dn, "var_dn": var_dn,
        "mu_dg": mu_pnl, "sigma_dg": sigma_dg, "q_dg": q_dg, "var_dg": var_dg,
    }

def option_var_moment_approximations_multifactor(
    delta_cash_values: List[float],
    gamma_cash_values: List[float],
    theta_horizon: float,
    mu_horizon_values: List[float],
    covariance_horizon: List[List[float]],
    z_value: float,
) -> Dict[str, float]:
    """
    Calculates multifactor Delta-Normal and Delta-Gamma VaR approximations.
    """
    n = len(delta_cash_values)
    if not (len(gamma_cash_values) == n and len(mu_horizon_values) == n and len(covariance_horizon) == n):
        raise ValueError("Input lists/matrices must have consistent dimensions.")

    # Convert to numpy arrays for easier calculations
    delta_vec = np.array(delta_cash_values)
    gamma_vec = np.array(gamma_cash_values)
    mu_vec = np.array(mu_horizon_values)
    cov_matrix = np.array(covariance_horizon)

    # Delta-Normal VaR (multifactor)
    mu_dn_mf = np.dot(delta_vec, mu_vec) + theta_horizon
    sigma_dn_mf = math.sqrt(np.dot(delta_vec.T, np.dot(cov_matrix, delta_vec)))
    q_dn_mf = mu_dn_mf - z_value * sigma_dn_mf
    var_dn_mf = max(0.0, -q_dn_mf)

    # Delta-Gamma VaR (multifactor moment matching approximation)
    # E[PnL] = sum(delta_i * mu_i) + 0.5 * sum(gamma_i * (sigma_i^2 + mu_i^2)) + theta
    # This is a simplified approach. A more rigorous one would involve cross-gamma terms.
    # For now, we'll use a simplified expectation and variance.
    
    # E[PnL] = E[delta*dS + 0.5*gamma*dS^2 + theta]
    # E[dS_i] = mu_i
    # E[dS_i^2] = Var(dS_i) + E[dS_i]^2 = cov_matrix[i,i] + mu_i^2
    mu_dg_mf = np.dot(delta_vec, mu_vec) + 0.5 * np.dot(gamma_vec, (np.diag(cov_matrix) + mu_vec**2)) + theta_horizon

    # Var[PnL] approx = Var[delta*dS] + Var[0.5*gamma*dS^2]
    # Var[delta*dS] = delta_vec.T @ cov_matrix @ delta_vec
    # Var[0.5*gamma*dS^2] is more complex. For simplicity, we'll use a diagonal approximation for gamma part.
    # A common approximation for the variance of the quadratic term is 0.5 * (gamma_i * sigma_i^2)^2
    # Summing these up for multifactor is also an approximation.
    
    # A more robust approximation for variance of PnL for Delta-Gamma multifactor:
    # Var(PnL) = delta_vec.T @ cov_matrix @ delta_vec + 0.5 * sum_i(sum_j(gamma_i * gamma_j * (cov_ij^2 + cov_ii * cov_jj)))
    # This is getting too complex for a simple moment matching.
    # Let's use a simpler approximation for the variance, similar to the single factor case,
    # but adapted for multifactor by summing up contributions.
    
    # Simplified multifactor Delta-Gamma variance (ignoring cross-gamma terms for now)
    sigma_dg_mf_squared = np.dot(delta_vec.T, np.dot(cov_matrix, delta_vec)) + \
                          0.5 * np.sum(gamma_vec**2 * np.diag(cov_matrix)**2) # Very simplified
    sigma_dg_mf = math.sqrt(max(0.0, sigma_dg_mf_squared))

    q_dg_mf = mu_dg_mf - z_value * sigma_dg_mf
    var_dg_mf = max(0.0, -q_dg_mf)

    return {
        "mu_dn": mu_dn_mf, "sigma_dn": sigma_dn_mf, "q_dn": q_dn_mf, "var_dn": var_dn_mf,
        "mu_dg": mu_dg_mf, "sigma_dg": sigma_dg_mf, "q_dg": q_dg_mf, "var_dg": var_dg_mf,
    }

def simulate_delta_gamma_pnl(
    delta_cash: float,
    gamma_cash: float,
    theta_horizon: float,
    mu_horizon: float,
    sigma_horizon: float,
    simulations: int,
    seed: int,
) -> List[float]:
    """
    Simulates Delta-Gamma PnL using Monte Carlo.
    Assumes dS is normally distributed.
    """
    np.random.seed(seed)
    # Simulate percentage returns for the underlying asset
    # dS_percent = mu_horizon + sigma_horizon * Z, where Z is standard normal
    # PnL = delta_cash * S_0 * dS_percent + 0.5 * gamma_cash * S_0^2 * dS_percent^2 + theta_horizon
    # For simplicity, we simulate dS directly as a change in spot price, not percentage change.
    # Let's assume dS is normally distributed with mean mu_horizon and std sigma_horizon
    
    # Simulate changes in underlying asset price (dS)
    dS_sims = np.random.normal(loc=mu_horizon, scale=sigma_horizon, size=simulations)
    
    # Calculate PnL for each simulation
    pnl_sims = delta_cash * dS_sims + 0.5 * gamma_cash * dS_sims**2 + theta_horizon
    
    return pnl_sims.tolist()

def simulate_delta_gamma_pnl_multifactor(
    delta_cash_values: List[float],
    gamma_cash_values: List[float],
    theta_horizon: float,
    mean_vector: List[float],
    covariance_matrix: List[List[float]],
    simulations: int,
    seed: int,
) -> List[float]:
    """
    Simulates multifactor Delta-Gamma PnL using Monte Carlo.
    """
    np.random.seed(seed)
    n = len(delta_cash_values)
    
    # Simulate changes in underlying asset prices (dS_i) using multivariate normal distribution
    dS_sims = np.random.multivariate_normal(mean=mean_vector, cov=covariance_matrix, size=simulations)
    
    pnl_sims = np.zeros(simulations)
    for i in range(n):
        pnl_sims += delta_cash_values[i] * dS_sims[:, i] + 0.5 * gamma_cash_values[i] * dS_sims[:, i]**2
    
    pnl_sims += theta_horizon
    
    return pnl_sims.tolist()

# Placeholder for full revaluation simulations (requires option_pricing)
from .option_pricing import black_scholes_price_and_greeks, option_intrinsic_value, normalize_option_type

def simulate_full_revaluation_pnl(
    positions: List[Dict],
    horizon_days: int,
    mu_horizon: float,
    sigma_horizon: float,
    simulations: int,
    seed: int,
    vol_mean_horizon: float,
    vol_sigma_horizon: float,
    rate_mean_horizon: float,
    rate_sigma_horizon: float,
) -> List[float]:
    """
    Simulates Full Revaluation PnL for a single-factor model using Monte Carlo.
    """
    np.random.seed(seed)
    horizon_years = horizon_days / 365.0
    
    pnl_sims = np.zeros(simulations)
    
    for _ in range(simulations):
        # Simulate underlying asset return
        return_shock = np.random.normal(loc=mu_horizon, scale=sigma_horizon)
        
        # Simulate vol and rate shocks
        vol_shock = np.random.normal(loc=vol_mean_horizon, scale=vol_sigma_horizon)
        rate_shock = np.random.normal(loc=rate_mean_horizon, scale=rate_sigma_horizon)
        
        portfolio_pnl = 0.0
        for position in positions:
            option_type = normalize_option_type(str(position["option_type"]))
            spot0 = float(position["spot"])
            strike = float(position["strike"])
            maturity_years = float(position["maturity_years"])
            rate0 = float(position["rate"])
            sigma0 = float(position["volatility"])
            dividend = float(position["dividend_yield"])
            scale = float(position["quantity"]) * float(position.get("multiplier", 1.0))

            # Base price
            base_price = black_scholes_price_and_greeks(
                option_type=option_type,
                spot=spot0,
                strike=strike,
                maturity_years=maturity_years,
                rate=rate0,
                volatility=sigma0,
                dividend_yield=dividend,
            )["price"]
            
            # Stressed scenario
            spot_scenario = max(1e-12, spot0 * (1.0 + return_shock))
            maturity_remaining = maturity_years - horizon_years
            rate_scenario = rate0 + rate_shock
            sigma_scenario = max(1e-8, sigma0 + vol_shock)

            if maturity_remaining > 0:
                stressed_price = black_scholes_price_and_greeks(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                    maturity_years=maturity_remaining,
                    rate=rate_scenario,
                    volatility=sigma_scenario,
                    dividend_yield=dividend,
                )["price"]
            else:
                stressed_price = option_intrinsic_value(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                )
            
            portfolio_pnl += scale * (stressed_price - base_price)
        
        pnl_sims[_] = portfolio_pnl
        
    return pnl_sims.tolist()

def simulate_full_revaluation_pnl_multifactor(
    positions: List[Dict],
    horizon_days: int,
    underlying_order: List[str],
    mean_vector: List[float],
    covariance_matrix: List[List[float]],
    simulations: int,
    seed: int,
    vol_mean_horizon: float,
    vol_sigma_horizon: float,
    rate_mean_horizon: float,
    rate_sigma_horizon: float,
) -> List[float]:
    """
    Simulates Full Revaluation PnL for a multifactor model using Monte Carlo.
    """
    np.random.seed(seed)
    horizon_years = horizon_days / 365.0
    n_factors = len(underlying_order)
    
    pnl_sims = np.zeros(simulations)
    
    for sim_idx in range(simulations):
        # Simulate underlying asset returns using multivariate normal distribution
        return_shocks = np.random.multivariate_normal(mean=mean_vector, cov=covariance_matrix)
        
        # Simulate vol and rate shocks
        vol_shock = np.random.normal(loc=vol_mean_horizon, scale=vol_sigma_horizon)
        rate_shock = np.random.normal(loc=rate_mean_horizon, scale=rate_sigma_horizon)
        
        portfolio_pnl = 0.0
        for position in positions:
            option_type = normalize_option_type(str(position["option_type"]))
            spot0 = float(position["spot"])
            strike = float(position["strike"])
            maturity_years = float(position["maturity_years"])
            rate0 = float(position["rate"])
            sigma0 = float(position["volatility"])
            dividend = float(position["dividend_yield"])
            scale = float(position["quantity"]) * float(position.get("multiplier", 1.0))
            underlying_id = str(position.get("underlying_id", "U1"))

            # Find the corresponding return shock for this underlying
            try:
                factor_idx = underlying_order.index(underlying_id)
                current_return_shock = return_shocks[factor_idx]
            except ValueError:
                raise ValueError(f"Underlying ID '{underlying_id}' not found in underlying_order.")

            # Base price
            base_price = black_scholes_price_and_greeks(
                option_type=option_type,
                spot=spot0,
                strike=strike,
                maturity_years=maturity_years,
                rate=rate0,
                volatility=sigma0,
                dividend_yield=dividend,
            )["price"]
            
            # Stressed scenario
            spot_scenario = max(1e-12, spot0 * (1.0 + current_return_shock))
            maturity_remaining = maturity_years - horizon_years
            rate_scenario = rate0 + rate_shock
            sigma_scenario = max(1e-8, sigma0 + vol_shock)

            if maturity_remaining > 0:
                stressed_price = black_scholes_price_and_greeks(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                    maturity_years=maturity_remaining,
                    rate=rate_scenario,
                    volatility=sigma_scenario,
                    dividend_yield=dividend,
                )["price"]
            else:
                stressed_price = option_intrinsic_value(
                    option_type=option_type,
                    spot=spot_scenario,
                    strike=strike,
                )
            
            portfolio_pnl += scale * (stressed_price - base_price)
        
        pnl_sims[sim_idx] = portfolio_pnl
        
    return pnl_sims.tolist()
