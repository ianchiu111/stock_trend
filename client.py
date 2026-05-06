"""
台股企業與產業資訊儀表板 (Stock Dashboard)
>>> streamlit run client.py
"""

import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ==========================================
# 1. 頁面基本設定
# ==========================================
st.set_page_config(page_title="證券資訊儀表板", page_icon="📈", layout="wide")

# ==========================================
# 2. Functions
# ==========================================
@st.cache_data
def load_data(symbol: str):
    file_path = f"stock/database/twse/{symbol}_twse_recent_data.csv"
    
    # 為了測試方便，如果找不到指定檔案，且有提供 0050 範例檔，則 fallback
    if not os.path.exists(file_path):
        if symbol == "0050" and os.path.exists("0050_twse_recent_data.csv"):
            file_path = "0050_twse_recent_data.csv"
        else:
            return None
    
    try:
        df = pd.read_csv(file_path, encoding="utf-8-sig")
        
        # 假設資料庫中有 'Date' 欄位，若名稱不同請依實際狀況修改
        if 'Date' not in df.columns:
            # 若原始資料為證交所格式，可能日期欄位名稱不同，請替換
            df.rename(columns={'日期': 'Date'}, inplace=True) 

        df['Date'] = pd.to_datetime(df['Date'].astype(str), format='%Y%m%d', errors='coerce')
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        
        # 定義需要轉數值的欄位
        numeric_cols = [
            '收盤價', '開盤價', '最高價', '最低價', '成交股數', 
            '成交金額', '成交筆數', '本益比', '最後揭示買量', '最後揭示賣量'
        ]
        
        # 清理並轉換數值 (處理逗號與缺失值 '--')
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('--', ''), errors='coerce')
                
        # 衍生欄位計算
        df['成交張數'] = df['成交股數'] / 1000
        df['每筆平均張數'] = df['成交張數'] / df['成交筆數'] # 大戶/散戶動向指標
        
        # 計算移動平均線
        df['MA5'] = df['收盤價'].rolling(window=5).mean()
        df['MA20'] = df['收盤價'].rolling(window=20).mean()
        df['MA60'] = df['收盤價'].rolling(window=60).mean()
        
        # 成交量均線
        df['VMA5'] = df['成交張數'].rolling(window=5).mean()
        
        return df
    
    except Exception as e:
        st.error(f"讀取資料時發生錯誤: {e}")
        return None

def load_explanation():
    """
    用來撰寫專有名詞說明的函式，讓使用者可以更了解圖表中各個指標的意義
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("補充說明")
    st.sidebar.markdown("""
    <div style="font-size: 12px; line-height: 1.5; color: #000000;">
        <ul>
            <li><b>證券代碼</b>：台股股票代碼或 ETF。</li>
            <li><b>本益比</b>：衡量股票潛在價值的指標，越低表示越物超所值。</li>
            <li><b>K線圖</b>：呈現開盤、最高、最低、收盤四種價格。紅升綠跌。</li>
            <li><b>移動平均線 (MA)</b>：平滑價格波動以辨識趨勢，如 MA5(周)、MA20(月)。</li>
            <li><b>成交量</b>：特定期間內的股票交易總數（1張 = 1000股）。</li>
            <li><b>每筆均張</b>：成交張數 ÷ 成交筆數。數值低暗示散戶交易較多。</li>
            <li><b>最後揭示量</b>：用來決定最後的收盤價，可反映市場買賣情緒。</li>
        </ul>
    </div>
    <div style="font-size: 10px; line-height: 1.5; color: #888888;">
        <p>本資訊僅供參考，請謹慎評估後再做決策。</p>
    </div>
                        
    """, unsafe_allow_html=True)


# ==========================================
# 3. 側邊欄設定 (使用者控制區)
# 我想要拆成上下兩部分
# 第一部分是使用者控制區，讓使用者輸入參數
# 第二部分是文字說明區，讓我可以了解什麼是<某特殊專有名詞>
# ==========================================
st.sidebar.title("📈 證券分析參數設定")
symbol_input = st.sidebar.text_input("輸入證券代碼", value="0050")

# 獲取資料
df = load_data(symbol_input)

if df is not None and not df.empty:
    # 日期選擇器
    min_date = df.index.min().date()
    max_date = df.index.max().date()
    
    # 預設顯示近三個月
    default_start = max_date - timedelta(days=90)
    if default_start < min_date:
        default_start = min_date
        
    start_date, end_date = st.sidebar.date_input(
        "選擇觀察期間",
        value=[default_start, max_date],
        min_value=min_date,
        max_value=max_date
    )
    
    # 根據日期篩選資料
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    filtered_df = df.loc[mask]

    # ==========================================
    # 4. 主畫面 Dashboard 渲染
    # ==========================================
    stock_name = df["證券名稱"].iloc[0]
    st.subheader(f"📊 {stock_name} ({symbol_input}) 投資儀表板")
    
    # 最新一日資料摘要
    latest_data = filtered_df.iloc[-1]
    prev_data = filtered_df.iloc[-2] if len(filtered_df) > 1 else latest_data
    
    col1, col2, col3, col4 = st.columns(4)
    price_diff = latest_data['收盤價'] - prev_data['收盤價']
    price_pct = (price_diff / prev_data['收盤價']) * 100
    
    col1.metric("收盤價", f"{latest_data['收盤價']:.2f}", f"{price_diff:.2f} ({price_pct:.2f}%)")
    col2.metric("成交量 (張)", f"{latest_data['成交張數']:,.0f}", f"{latest_data['成交張數'] - prev_data['成交張數']:,.0f}")
    if '本益比' in latest_data:
        col3.metric("本益比 (P/E)", f"{latest_data['本益比']:.2f}")
    if '每筆平均張數' in latest_data:
        col4.metric("每筆均張 (籌碼流向)", f"{latest_data['每筆平均張數']:.2f} 張/筆")

    st.markdown("---")

    # ---------------------------------------------------------
    # 模組一 & 二：價格趨勢與量能追蹤 (Plotly 互動雙軸 K線圖)
    # ---------------------------------------------------------
    st.subheader("1. 價格趨勢")
    
    # 建立上下兩個子圖 (K線 + 成交量)，共用X軸
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, subplot_titles=('K線與均線', '成交量'),
                        row_width=[0.2, 0.7])

    # 繪製 K 線
    fig.add_trace(go.Candlestick(
        x=filtered_df.index,
        open=filtered_df['開盤價'], high=filtered_df['最高價'],
        low=filtered_df['最低價'], close=filtered_df['收盤價'],
        name="K線",
        increasing_line_color='red', decreasing_line_color='green'
    ), row=1, col=1)

    # 繪製 MA
    fig.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df['MA5'], name='MA5', line=dict(color='orange', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df['MA20'], name='MA20', line=dict(color='blue', width=1.5)), row=1, col=1)

    # 繪製成交量 (根據收盤漲跌給予紅綠色)
    colors = ['red' if row['收盤價'] >= row['開盤價'] else 'green' for index, row in filtered_df.iterrows()]
    fig.add_trace(go.Bar(x=filtered_df.index, y=filtered_df['成交張數'], name='成交張數', marker_color=colors), row=2, col=1)
    
    # 繪製量均線 VMA5
    fig.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df['VMA5'], name='VMA5', line=dict(color='yellow', width=1.5)), row=2, col=1)

    # 版面設定：支援十字線連動 (Spikelines) 與深色背景
    fig.update_layout(
        height=650, 
        template="plotly_dark", 
        xaxis_rangeslider_visible=False,
        hovermode="x unified", # 讓滑鼠移過去時，一次顯示當天所有數據
        margin=dict(l=20, r=20, t=30, b=20)
    )
    # 隱藏週末/非交易日的空白 (Plotly 預設會顯示所有連續日期)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------
    # 模組三：估值與基本面輔助 (本益比河流圖)
    # ---------------------------------------------------------
    st.subheader("2. 估值區間 (本益比分析)")
    
    if '本益比' in filtered_df.columns and not filtered_df['本益比'].dropna().empty:
        fig_pe = go.Figure()
        
        # 繪製本益比變化線
        fig_pe.add_trace(go.Scatter(
            x=filtered_df.index, y=filtered_df['本益比'], 
            name='每日本益比', mode='lines', line=dict(color='cyan', width=2)
        ))
        
        # 加上平均本益比參考線
        mean_pe = filtered_df['本益比'].mean()
        fig_pe.add_hline(y=mean_pe, line_dash="dash", line_color="white", annotation_text=f"平均 PE: {mean_pe:.2f}")

        fig_pe.update_layout(
            height=300, template="plotly_dark", hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_pe, use_container_width=True)
    else:
        st.warning("此區間缺乏足夠的本益比資料進行繪製。")

    # ---------------------------------------------------------
    # 模組四：收盤情緒與微觀結構 (尾盤買賣氣勢)
    # ---------------------------------------------------------
    st.subheader("3. 收盤微觀結構分析")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**📊 籌碼流向：每筆平均成交張數**")
        fig_avg_lot = go.Figure(data=[
            go.Scatter(x=filtered_df.index, y=filtered_df['每筆平均張數'], fill='tozeroy', line_color='magenta')
        ])
        fig_avg_lot.update_layout(height=250, template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0))
        fig_avg_lot.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        st.plotly_chart(fig_avg_lot, use_container_width=True)

    with col_b:
        st.markdown("**⚖️ 最後揭示買賣力道 (最新交易日)**")
        
        bid_vol = latest_data.get('最後揭示買量', 0)
        ask_vol = latest_data.get('最後揭示賣量', 0)
        
        if pd.isna(bid_vol): bid_vol = 0
        if pd.isna(ask_vol): ask_vol = 0
            
        total_vol = bid_vol + ask_vol
        if total_vol > 0:
            bid_pct = (bid_vol / total_vol) * 100
            ask_pct = (ask_vol / total_vol) * 100
            
            st.markdown(f"**買方掛單量 (Bid):** {bid_vol:,.0f} 張 ({bid_pct:.1f}%)")
            st.progress(bid_pct / 100)
            
            st.markdown(f"**賣方掛單量 (Ask):** {ask_vol:,.0f} 張 ({ask_pct:.1f}%)")
            st.progress(ask_pct / 100)
            
            if bid_vol > ask_vol * 1.5:
                st.success("🔥 買量遠大於賣量（買氣過剩）")
            elif ask_vol > bid_vol * 1.5:
                st.error("⚠️ 賣量遠大於買量（賣壓沉重）")
            else:
                st.info("⚖️ 買賣力道相對均衡。")
        else:
            st.write("無最後揭示買賣量資料。")
    
    # ---------------------------------------------------------
    # 模組五：參數說明
    # ---------------------------------------------------------
    load_explanation() 

else:
    st.warning("找不到此股票代碼的資料，或資料格式錯誤。請確認檔案路徑與名稱是否正確。")