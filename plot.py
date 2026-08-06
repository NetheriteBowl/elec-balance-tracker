import csv
import os
from datetime import datetime
import plotly.graph_objects as go
from plotly.offline import plot
import webbrowser

DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "elec_history.csv")
PUBLIC_DIR = "public"
HTML_FILE = os.path.join(PUBLIC_DIR, "index.html")  # 部署为 Pages 主页

def load_data():
    dates, balances = [], []
    if not os.path.exists(CSV_FILE):
        return [], []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 3:
                try:
                    date_obj = datetime.strptime(row[0], '%Y-%m-%d').date()
                    dates.append(date_obj)
                    balances.append(float(row[2]))
                except:
                    continue
    return dates, balances

def calc_stats(dates, balances):
    if not balances:
        return {}
    stats = {
        '总天数': len(dates),
        '首日余额': balances[0],
        '末日余额': balances[-1],
        '最大余额': max(balances),
        '最小余额': min(balances),
        '平均余额': sum(balances) / len(balances),
    }
    if len(balances) > 1:
        stats['总消耗'] = balances[0] - balances[-1]
        stats['日平均消耗'] = stats['总消耗'] / (len(balances) - 1)
    else:
        stats['总消耗'] = 0
        stats['日平均消耗'] = 0
    return stats

def create_plot(dates, balances, stats):
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=balances,
        mode='lines+markers',
        name='余额',
        line=dict(color='#3498db', width=2),
        marker=dict(size=6, color='#2980b9'),
        hovertemplate='日期: %{x|%Y-%m-%d}<br>余额: %{y:.2f} 度<extra></extra>'
    ))
    fig.update_layout(
        title='电费余额变化趋势',
        xaxis=dict(title='日期', type='date', tickformat='%Y-%m-%d', tickangle=45),
        yaxis=dict(title='余额 (度)', tickformat='.0f', dtick=10),
        hovermode='x unified',
        template='plotly_white',
        height=600,
        margin=dict(l=60, r=40, t=80, b=100),
    )
    stats_text = (
        f"📊 统计信息<br>"
        f"总天数: {stats['总天数']}<br>"
        f"首日余额: {stats['首日余额']:.2f} 度<br>"
        f"末日余额: {stats['末日余额']:.2f} 度<br>"
        f"最大余额: {stats['最大余额']:.2f} 度<br>"
        f"最小余额: {stats['最小余额']:.2f} 度<br>"
        f"平均余额: {stats['平均余额']:.2f} 度<br>"
        f"总消耗: {stats['总消耗']:.2f} 度<br>"
        f"日平均消耗: {stats['日平均消耗']:.2f} 度"
    )
    fig.add_annotation(
        x=1, y=0, xref='paper', yref='paper',
        text=stats_text, showarrow=False, align='left',
        font=dict(size=12, color='#2c3e50'),
        bgcolor='rgba(255,255,255,0.85)',
        bordercolor='#bdc3c7', borderwidth=1, borderpad=8,
        xanchor='right', yanchor='bottom', yshift=-20, xshift=-20
    )
    # 写入 HTML（内联所有资源，可独立浏览）
    plot(fig, filename=HTML_FILE, auto_open=False, include_plotlyjs='cdn')
    print(f"✅ 图表已保存到 {HTML_FILE}")

def main():
    dates, balances = load_data()
    stats = calc_stats(dates, balances)
    create_plot(dates, balances, stats)

if __name__ == "__main__":
    main()