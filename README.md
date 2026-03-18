# Risk-Calculator (ветка `Misha`)

Квант-ядро риск-калькулятора для расчета VaR/ES, опционных греков и Option VaR.
Проект сейчас реализован как CLI-приложение, а модули в `riskcalc/` используются как переиспользуемый backend-слой для будущей web/API-обвязки.

## Что уже реализовано

1. `Historical VaR + ES` (дискретный, без интерполяции).
2. `Parametric VaR` (normal, one-tailed, confidence: 95%/99%).
3. `LVaR` (normal/stressed liquidation cost).
4. `Linear unwind adjustment` на период ликвидации.
5. `Black-Scholes + Greeks` (европейские опционы, одиночная позиция и портфель).
6. `Option VaR`:
   - Delta-Normal
   - Delta-Gamma (moment matching)
   - Monte Carlo (Delta-Gamma)
   - Monte Carlo Full Revaluation (single/multifactor, optional vol/rate shocks)
   - Deterministic stress scenarios (стандартные + пользовательские)
   - Risk attribution (marginal/component VaR по факторам).
7. `Rolling backtest` для VaR/ES:
   - Kupiec POF
   - Christoffersen Independence
   - Christoffersen Conditional Coverage
   - ES diagnostics на breach-днях.

## Архитектура

- [`main.py`](./main.py): orchestration и CLI-сценарии; внутри есть вспомогательные функции для PnL и базовых VaR/ES/LVaR.
- [`riskcalc/option_pricing.py`](./riskcalc/option_pricing.py): BSM-прайсинг и греки.
- [`riskcalc/option_var.py`](./riskcalc/option_var.py): Delta-Normal/Delta-Gamma/MC Full Revaluation (single и multifactor).
- [`riskcalc/backtesting.py`](./riskcalc/backtesting.py): rolling VaR/ES backtest + статистические тесты.
- [`riskcalc/risk_attribution.py`](./riskcalc/risk_attribution.py): marginal/component VaR.
- [`riskcalc/stress_testing.py`](./riskcalc/stress_testing.py): deterministic stress engine.
- [`tests/test_riskcalc_extensions.py`](./tests/test_riskcalc_extensions.py): unit-тесты новых расширений.

## Быстрый запуск

Требования:

- Python 3.10+

Запуск:

```bash
cd /Users/ivanovmichael/Documents/Risk-Calculator
python3 main.py
```

Тесты:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Контракты данных (для интеграции с парсером и сайтом)

### 1) Базовые ряды для VaR/ES

Калькулятор может работать с:

1. `prices` (из парсера) -> преобразуются в денежный `P&L` через разности цен.
2. `pnl` (уже денежный ряд).
3. `returns` + размер позиции -> денежный `P&L`.

Важно:

- знак: `P&L < 0` = убыток.
- VaR/ES всегда отдаются как положительная величина потерь.

### 2) Формат опционной позиции

Для `Option VaR` и stress engine используется список позиций с такой структурой:

```python
{
    "underlying_id": "U1",      # str
    "option_type": "call",      # "call"/"put" (допускаются c/p на входе CLI)
    "spot": 100.0,              # float > 0
    "strike": 100.0,            # float > 0
    "maturity_years": 0.5,      # float > 0
    "rate": 0.05,               # decimal (5% -> 0.05)
    "volatility": 0.2,          # decimal (20% -> 0.20)
    "dividend_yield": 0.0,      # decimal
    "quantity": 1.0,            # float (можно < 0 для short)
    "multiplier": 1.0           # float
}
```

### 3) Формат stress-сценария

```python
{
    "name": "Crash -15% + Vol +10pp",
    "underlying_shocks": {"U1": -0.15, "U2": -0.15},  # доходности за горизонт
    "volatility_shift": 0.10,  # additive (10pp)
    "rate_shift": 0.00         # additive (в долях, 100 bps = 0.01)
}
```

## Интеграция с парсером и фронтом

Рекомендуемый pipeline:

1. Парсер готовит чистые ряды: `prices`/`returns`, и метаданные инструментов.
2. Backend-adapter нормализует формат:
   - проценты -> decimal;
   - даты и частоты (дневные данные для текущих моделей);
   - выравнивание рядов по длине/календарю.
3. Adapter вызывает quant-функции из `main.py` и `riskcalc/*`.
4. Результаты сериализуются в JSON для сайта (карточки метрик, графики, backtest block, stress table).

Для фронтенда полезно держать стабильный JSON-контракт на стороне backend-обвязки:

- `var_loss`, `es_loss`, `q_alpha_pnl`, `mu`, `sigma`
- `greeks` и `cash_greeks`
- `mc_var`, `mc_es`
- `backtest: {exceptions, p_value, verdict, ...}`
- `stress_results: [{name, total_pnl, stressed_value}]`
- `risk_attribution: [{factor, marginal_var, component_var, component_share_pct}]`

## Ограничения текущей версии

1. Confidence поддержан только `95%` и `99%`.
2. Модели рассчитаны на дневной шаг наблюдений.
3. Опционы: европейские, BSM.
4. Rolling backtest требует `window >= 20` и `len(pnl) > window`.
5. В проекте пока нет отдельного REST-слоя; текущий вход через CLI.

## Минимальный пример программного вызова (без CLI)

```python
from main import pnl_from_prices, historical_var_discrete, expected_shortfall_discrete
from riskcalc.backtesting import rolling_historical_var_es, christoffersen_conditional_coverage_test

prices = [100, 101, 99, 98, 102, 101]
pnl = pnl_from_prices(prices, position_size=1.0)
var_loss, var_pnl, k = historical_var_discrete(pnl, 0.95)
es_loss, es_pnl, tail = expected_shortfall_discrete(pnl, 0.95)

history = rolling_historical_var_es(pnl=[-1, 2, -2, 1, -1, 3, -2, 1, -1, 2, -2, 1, -1, 2, -3, 1, 2, -1, 1, -2, 2], confidence=0.95, window=20)
cc = christoffersen_conditional_coverage_test(history["exceptions"], alpha=0.05)
print(var_loss, es_loss, cc["verdict"])
```

## Ближайший технический шаг (по желанию)

Сделать thin backend-layer (`service.py`) с функциями, которые принимают/возвращают уже готовый JSON-контракт. Тогда фронтендер сможет подключаться напрямую к стабильным endpoint-структурам без знания внутренних квант-функций.
