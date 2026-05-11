# Service Roadmap

## Goal

Move the project from a multi-tool risk calculator toward a user-facing decision-support service.

## Product Direction

The mathematical core is already broad enough for a strong academic project.  
The next stage should focus on service intelligence, interpretability, and easier data input.

## Prioritized Enhancements

### 1. Risk Copilot

Purpose:

- explain results in plain language
- tell the user what metric matters most
- suggest the next analytical step

Examples:

- "The main risk comes from concentration in one asset."
- "Monte Carlo confirms the analytical estimate."
- "Stress losses are materially larger than daily VaR."

### 2. Hedge Constructor

Purpose:

- compare unhedged and hedged risk
- show candidate hedge instruments
- display before/after risk metrics

Potential coverage:

- options
- futures / SPFI
- bond / swap package

### 3. Excel Input Layer

Purpose:

- let users upload prices or portfolio composition
- reduce manual entry friction
- make the service usable for non-technical users

Initial target flows:

- One Asset: upload a price series from Excel
- Portfolio: upload tickers / weights from Excel

### 4. Explainability and Result Highlighting

Purpose:

- make important results visually obvious
- help non-experts interpret good vs bad outcomes quickly

Examples:

- green / yellow / red risk status
- "main takeaway" summary block
- badges for concentration, stress sensitivity, and hedge effect

## What Is Included Inside Risk Copilot

Risk Copilot is the main service-intelligence layer.
It can include:

- concentration warnings
- diversification warnings
- tail-risk comments
- liquidity warnings
- suggestions for the next analytical step

These diagnostics are part of Copilot itself, not a separate standalone module.

## Recommended Implementation Order

1. Excel input for One Asset and Portfolio
2. Reusable explainability layer for existing outputs
3. Risk Copilot summaries and diagnostics
4. Hedge Constructor workflows

## Non-Goals Right Now

- expanding the mathematical engine with many more models
- adding more disconnected tabs
- adding ML just for complexity

## Success Criterion

The service should not only calculate risk, but also help an inexperienced user understand:

- what happened
- why it matters
- what they should do next
