import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import logging
from scipy import stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
def run_elite_quant_pipeline():
    logging.info("Initializing Quant Performance Pipeline")
    try:
        df_trader = pd.read_csv('historical_data.csv')
        df_sentiment = pd.read_csv('fear_greed_index.csv')
    except FileNotFoundError as e:
        logging.error(f"Data ingestion failed: {e}")
        return

    trader_time_col = 'Timestamp.1' if 'Timestamp.1' in df_trader.columns else 'Timestamp'
    df_trader['clean_date'] = pd.to_datetime(df_trader[trader_time_col], unit='ms', errors='coerce').dt.date
    df_sentiment['clean_date'] = pd.to_datetime(df_sentiment['timestamp'], unit='s', errors='coerce').dt.date

    df_merged = pd.merge(df_trader, df_sentiment, on='clean_date', how='inner').dropna(subset=['Closed PnL', 'classification'])
    if df_merged.empty:
        logging.warning("Intersection pipeline generated an empty dataset. Check timestamp scaling.")
        return


    df_merged['is_win'] = (df_merged['Closed PnL'] > 0).astype(int)
    df_merged['gross_profit'] = df_merged['Closed PnL'].apply(lambda x: x if x > 0 else 0)
    df_merged['gross_loss'] = df_merged['Closed PnL'].apply(lambda x: abs(x) if x < 0 else 0)


    sentiment_groups = [group['Closed PnL'].values for name, group in df_merged.groupby('classification')]    
    p_value = 1.0
    if len(sentiment_groups) > 1:
        stat, p_value = stats.kruskal(*sentiment_groups)
        logging.info(f"Statistical Analysis Complete. Kruskal-Wallis p-value: {p_value:.6f}")

    df_merged['is_high_freq'] = df_merged.groupby('account')['Trade ID'].transform('count') > 10
    
    def calculate_regime_metrics(group):
        total_trades = len(group)
        win_rate = (group['is_win'].mean() * 100).round(2)
        total_pnl = group['Closed PnL'].sum()
        avg_pnl = group['Closed PnL'].mean()
        
        pnl_std = group['Closed PnL'].std()
        risk_adjusted_return = (avg_pnl / pnl_std).round(4) if pnl_std > 0 else 0
        sum_profit = group['gross_profit'].sum()
        sum_loss = group['gross_loss'].sum()
        profit_factor = (sum_profit / sum_loss).round(2) if sum_loss > 0 else (np.inf if sum_profit > 0 else 1.0)        
        return pd.Series({
            'Total_Trades': total_trades,
            'Total_PnL_USD': round(total_pnl, 2),
            'Win_Rate_Pct': win_rate,
            'Profit_Factor': profit_factor,
            'Risk_Adjusted_Ratio': risk_adjusted_return
        })

    regime_profile = df_merged.groupby('classification').apply(calculate_regime_metrics).reset_index()
    print("                      METRIC ALPHA MATRIX GENERATED       ")
    print(regime_profile.to_string(index=False))
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    sns.boxenplot(data=df_merged, x='classification', y='Closed PnL', ax=axes[0], palette='magma')
    axes[0].set_title('PnL Distribution Mechanics by Market Regime', fontsize=12, fontweight='bold')
    axes[0].set_yscale('symlog')
    ax2 = axes[1]
    ax3 = ax2.twinx()
    
    sns.barplot(data=regime_profile, x='classification', y='Win_Rate_Pct', ax=ax2, alpha=0.7, color='teal')
    sns.lineplot(data=regime_profile, x='classification', y='Profit_Factor', ax=ax3, color='crimson', marker='o', linewidth=2.5)
    
    ax2.set_title('Win Rate vs. Profit Factor Analysis', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Win Rate (%)', color='teal', fontweight='bold')
    ax3.set_ylabel('Profit Factor (Gross PnL Ratio)', color='crimson', fontweight='bold')
    plt.tight_layout()
    plt.savefig('quant_alpha_report.png', dpi=300)
    regime_profile.to_csv('quant_regime_matrix.csv', index=False)    
    return p_value

if __name__ == "__main__":
    run_elite_quant_pipeline()