# Risk Calculator (MOEX/SPFI)

A comprehensive risk management system designed for analyzing financial assets and portfolios on the Moscow Exchange (MOEX). The platform provides advanced risk metrics, including Value at Risk (VaR), Expected Shortfall (ES), and Liquidity-Adjusted VaR (LVaR), along with portfolio optimization tools.

## Features

### Single Asset Analysis
- **Risk Metrics**: Calculation of Parametric VaR, Historical VaR, and Expected Shortfall (CVaR).
- **Liquidity Risk**: Estimation of Liquidity-Adjusted VaR (LVaR) considering bid-ask spreads and liquidation periods (Normal & Stressed markets).
- **Backtesting**: Kupiec POF test to validate model accuracy.
- **Data Sources**: Integration with Tinkoff Invest API, manual data entry, or Geometric Brownian Motion simulation.

### Portfolio Optimization
- **Portfolio VaR**: Calculation of portfolio risk using the Variance-Covariance method.
- **Efficient Frontier**: Visualization of the risk-return trade-off and simulation of optimal portfolios.
- **Correlation Matrix**: Heatmap visualization of asset correlations.
- **Performance Analysis**: Cumulative returns comparison (Portfolio vs Individual Assets).

## Tech Stack

- **Backend**: Python 3.10, FastAPI, NumPy, Pandas, SciPy.
- **Frontend**: HTML5, Bootstrap 5, Plotly.js.
- **Data**: Tinkoff Invest API (t-tech-investments).
- **Containerization**: Docker, Docker Compose.

## Installation & Running

### Prerequisites
- Docker & Docker Compose
- Tinkoff Invest API Token (Read-only is sufficient)

### Quick Start

1. Clone newest files

2. Set up .env:
   - Create .env file and add there token TINKOFF_TOKEN=

3. Build and run the container:
   ```bash
   docker-compose up --build
   ```

4. Access the application:
   Open your browser and navigate to `http://localhost:8000` or `http://127.0.0.1:8000/` if first one is not working.

## Project Structure

```
├── services/
│   ├── portfolio_manager.py  # Portfolio calculations & Efficient Frontier
│   ├── risk_calculator.py    # Core risk metrics (VaR, ES, LVaR)
│   └── tinkoff_service.py    # API integration
├── templates/
│   └── index.html            # Frontend interface
├── main.py                   # FastAPI entry point
├── Dockerfile
└── requirements.txt
```

