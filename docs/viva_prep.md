# Major Project Defense: Viva Q&A Bank

Prepare for your defense by reviewing these potential academic and technical questions.

### Question 1: Why use an LSTM for forecasting instead of a simpler model like ARIMA or Random Forest?
**Answer Strategy**: 
- Emphasize the temporal complexity of ICU variables.
- "ARIMA handles univariate time series well, but ventilator parameters and patient vitals are highly multivariate. Random Forests ignore sequential dependencies. Bidirectional LSTMs capture the long-term context (e.g. past 3 hours of vitals) and the non-linear relationship between FiO2/PEEP adjustments and SpO2 outcomes."
- Mention the focal loss technique you implemented to handle the 1.9% class imbalance of hypoxia risk.

### Question 2: How does the Digital Twin ensure patient safety?
**Answer Strategy**:
- "RL agents (like PPO) are notorious for exploring unsafe parameters. The Digital Twin acts as an intermediate sandbox validator. When the AI suggests raising PEEP, the Twin runs a physiological simulation. If the Twin calculates a drop in blood pressure or poor oxygenation, it throws a `risk_flag`, dropping the policy confidence and warning the clinician."

### Question 3: Why is Blockchain necessary here? Isn't a standard database enough?
**Answer Strategy**:
- "Standard databases are mutable—a DBA or hacker could delete a poor AI recommendation after an adverse patient event, destroying clinical traceability. Our SQLite hash-chain ledger simulates a permissioned blockchain. Every recommendation and clinician `ACCEPT/OVERRIDE` event is hashed via SHA-256 and chained to the previous block. This creates `cryptographic proof` that an action was taken, protecting the clinician's liability and ensuring the AI is fully accountable."

### Question 4: How are you managing class imbalance in the Hypoxia prediction?
**Answer Strategy**:
- Talk about the `clean_full_data_v2.csv` distribution.
- "Out of 800,000 rows, only about 2% represent genuine hypoxia risk events. If we used standard SparseCategoricalCrossentropy, the model would simply guess 'No Risk' every time and get 98% accuracy. We employed a `focal_loss` function which exponentially penalizes misclassifications on the minority class, raising our recall significantly."

### Question 5: What is the benefit of the dual-head LSTM architecture?
**Answer Strategy**:
- "Rather than training two separate models (one to predict exact SpO2, another to classify risk), a Dual-Head model shares the Bidirectional encoding layers. This allows the network to learn unified feature representations, saving compute resources (critical for edge deployment in an ICU) while providing both continuous tracking (`next_spo2`) and discrete clinical alerts (`hypoxia_risk`)."
