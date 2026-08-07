import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta

# ---------- 路径配置 ----------
DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "elec_history.csv")
PUBLIC_DIR = "public"
HTML_FILE = os.path.join(PUBLIC_DIR, "index.html")
os.makedirs(PUBLIC_DIR, exist_ok=True)

# ---------- 数据读取与处理 ----------
df = pd.read_csv(CSV_FILE, parse_dates=['date'])
df = df.sort_values('date').reset_index(drop=True)

# ---------- 计算每日消耗（只统计余额减少） ----------
df['consumption'] = (df['balance'] - df['balance'].shift(-1)).clip(lower=0).fillna(0)

# ---------- 统计信息（排除最新日期，因为它的消耗为0占位） ----------
valid_consumption = df['consumption'].iloc[:-1]   # 只统计有真实值的历史天数
stats = {
    '总天数': len(df),
    '有效消耗天数': len(valid_consumption),
    '平均每日消耗': valid_consumption.mean(),
    '最大日消耗': valid_consumption.max(),
    '最小日消耗': valid_consumption.min(),
    '总消耗': valid_consumption.sum(),
    '消耗标准差': valid_consumption.std(),
    '起始余额': df['balance'].iloc[0],
    '最新余额': df['balance'].iloc[-1],
}

stats_text = (
    f"<b>全部数据统计</b><br>"
    + "<br>".join(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}" for k, v in stats.items())
)

# ---------- 预测（基于近期平均消耗，不受充值干扰） ----------
recent_days = min(7, len(valid_consumption))   # 取最近7天，不足则取全部
avg_daily_consumption = valid_consumption.tail(recent_days).mean()
last_balance = df['balance'].iloc[-1]
last_date = df['date'].max()
future_dates = [last_date + timedelta(days=i+1) for i in range(7)]
future_pred = [last_balance - avg_daily_consumption * (i+1) for i in range(7)]

# ---------- 构建子图 ----------
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.7, 0.3],
    subplot_titles=("余额趋势与预测", "每日消耗")  # 保留子图标题
)

# 主图：实际余额
fig.add_trace(
    go.Scatter(x=df['date'], y=df['balance'], mode='lines+markers',
               name='实际余额', line=dict(color='blue'), marker=dict(size=4)),
    row=1, col=1
)
# 主图：预测余额
fig.add_trace(
    go.Scatter(x=future_dates, y=future_pred, mode='lines+markers',
               name='预测余额 (7天)', line=dict(color='red', dash='dash'),
               marker=dict(size=6, symbol='triangle-up')),
    row=1, col=1
)
# 下窄图：每日消耗
fig.add_trace(
    go.Bar(x=df['date'], y=df['consumption'], name='每日消耗',
           marker=dict(color='orange'), opacity=0.7),
    row=2, col=1
)

# ---------- 固定统计注释（右上角） ----------
fig.add_annotation(
    xref="paper", yref="paper",
    x=1, y=1,
    xanchor='left', yanchor='top',
    text=stats_text,
    showarrow=False,
    font=dict(size=10, color='darkgreen'),
    bgcolor='rgba(255,255,255,0.8)',
    bordercolor='black',
    borderwidth=1,
    align='left'
)

# ---------- 使用 rangeselector 切换范围 ----------
# 只给第一行的 x 轴加 rangeselector
fig.update_xaxes(
    rangeselector=dict(
        buttons=[
            dict(count=7, label="7d", step="day", stepmode="backward"),
            dict(count=14, label="14d", step="day", stepmode="backward"),
            dict(count=1, label="1m", step="month", stepmode="backward"),
            dict(count=3, label="3m", step="month", stepmode="backward"),
            dict(count=6, label="6m", step="month", stepmode="backward"),
            dict(step="all", label="全部")
        ],
    ),
    rangeslider=dict(visible=False),
    row=1, col=1   # ← 限定只改第一行
)

# 第二行的 x 轴关掉 rangeselector
fig.update_xaxes(
    rangeselector=dict(visible=False),
    row=2, col=1
)

# ---------- 整体布局（无总标题，调整边距） ----------
fig.update_layout(
    height=700,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=50, r=200, t=60, b=50),  # 顶部留空减少，给 rangeselector 更多空间
)
fig.update_yaxes(title_text="余额 (元)", row=1, col=1)
fig.update_yaxes(title_text="消耗 (元)", row=2, col=1)

# ---------- 保存 HTML ----------
fig.write_html(HTML_FILE)
print(f"HTML 已生成: {HTML_FILE}")