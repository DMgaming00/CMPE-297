# 📈 TimePulse — Multi-Horizon Time Series Forecasting & Telemetry Engine

An end-to-end CRISP-DM time series forecasting platform featuring multi-horizon predictions ($h=7..60$ days), expanding 95% confidence interval fans, classical additive signal decomposition, and walk-forward backtesting tournaments.

---

## 📸 Comprehensive Visual Tour

### 1. Live Forecast Studio & Scenario Simulation
*Interactive multi-step horizon fans ($h=7..60$ days) with weather demand surge multipliers ($0..+50\%$), expanding 95% confidence bands, and telemetry anomaly flag markers ($> 3\sigma$).*
![Time Series Forecast Studio](./screenshots/timeseries_forecast_studio.png)

### 2. 6-Phase CRISP-DM Time Series Workflow Guide
*Interactive CRISP-DM lifecycle guide detailing Business Understanding through Operational Telemetry.*
![Time Series CRISP-DM](./screenshots/timeseries_crispdm_steps.png)

### 3. Classical Signal Decomposition & 40-Lag Autocorrelation
*Orthogonal additive decomposition ($Y_t = \text{Trend}_t + \text{Seasonal}_t + \text{Residual}_t$), ADF & KPSS stationarity tests, and 40-lag interactive ACF/PACF bar charts.*
![Time Series Decomposition](./screenshots/timeseries_decomposition_acf.png)

### 4. Walk-Forward Backtesting Leaderboard
*Multi-model tournament comparing LightGBM Lag GBDT (Champion MAPE: `2.84%`, MASE: `0.42`), Deep N-BEATS (`3.12%`), Prophet (`3.65%`), and SARIMAX (`4.18%`).*
![Time Series Tournament](./screenshots/timeseries_tournament_leaderboard.png)

### 5. Admin Telemetry & AutoResearch Optimizer
*Real-time server telemetry streams, execution latency metrics, and automated lag search hill-climbing.*
![Time Series Admin](./screenshots/timeseries_admin_autoresearch.png)

---

## 📐 Mathematical Foundations

1. **Additive Signal Decomposition**:
   $$Y_t = \text{Trend}_t + \text{Seasonal}_t + \text{Residual}_t$$
2. **Mean Absolute Scaled Error (MASE)**:
   $$\text{MASE} = \frac{\sum_{t=1}^n |y_t - \hat{y}_t|}{\frac{n}{n-m} \sum_{t=m+1}^n |y_t - y_{t-m}|}$$
3. **Autocorrelation Function (ACF)**:
   $$\rho_k = \frac{\sum_{t=k+1}^T (y_t - \bar{y})(y_{t-k} - \bar{y})}{\sum_{t=1}^T (y_t - \bar{y})^2}$$

---

## 🧠 Autonomous Skills Included

Pre-packaged in `skills/` and `.agents/skills/`:
* `time-series-analysis`: Temporal decomposition, stationarity tests, and lag modeling.
* `business-metrics-calculator`: SaaS and operational metric KPI calculators.
* `dashboard-specification`: Real-time telemetry monitoring designs.

---

## 🚀 Quick Start

```bash
# Backend (FastAPI on Port 8012)
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8012

# Frontend (Vite React on Port 5185)
cd frontend
npm install
npm run dev # Open http://localhost:5185/
```
