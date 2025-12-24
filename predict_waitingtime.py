import streamlit as st
import pandas as pd

# ==========================================
# 0. マスタデータ設定
# ==========================================
LOCATION_MASTER = {
    "A地区 (近隣)": 15,
    "B地区 (標準)": 30,
    "C地区 (遠方)": 45,
    "Dマンション": 25,
    "E駅前ビル": 35,
    "F団地": 50
}

# ==========================================
# 1. セッション状態の初期化
# ==========================================
if 'orders' not in st.session_state:
    st.session_state.orders = []

# ==========================================
# 2. 計算ロジック (回転数を廃止し、平均ペース計算へ変更)
# ==========================================
def calculate_wait_time(orders_list, driver_count):
    if not orders_list:
        return 30, 0, 0, 0
    
    times = [o["time"] for o in orders_list]
    num_orders = len(times)
    
    # 1. 平均往復時間の計算
    avg_round_trip = sum(times) / num_orders
    
    # 2. 平均片道時間の計算
    avg_one_way = avg_round_trip / 2
    
    # 3. 待ち係数の計算 (回転数ではなく、ドライバー1人あたりの負担件数)
    # (自分以外の注文数) ÷ ドライバー数
    # これにより "2人で手分けして消化する" スピードを計算
    waiting_factor = (num_orders - 1) / driver_count
    
    # 4. 計算式: (平均往復 × 待ち係数) + 平均片道
    # 意味: 「前の人たちが片付くまでの時間」 + 「自分の移動時間」
    raw_time = (avg_round_trip * waiting_factor) + avg_one_way
    
    # 最低保証 30分
    final_time = max(30, raw_time)
    
    return int(final_time), avg_round_trip, waiting_factor, raw_time

# ==========================================
# 3. UI構築
# ==========================================
st.title("🛵 リアルタイム待ち時間計算")

# --- サイドバー：入力エリア ---
with st.sidebar:
    st.header("📝 注文の追加")
    
    select_options = ["(場所を選択)"] + list(LOCATION_MASTER.keys()) + ["その他(手動入力)"]
    selected_loc = st.selectbox("配達先を選択", select_options)
    
    default_name = ""
    default_time = 30
    if selected_loc in LOCATION_MASTER:
        default_name = selected_loc
        default_time = LOCATION_MASTER[selected_loc]
    elif selected_loc == "その他(手動入力)":
        default_name = ""
        default_time = 30
    
    input_loc = st.text_input("地名・備考", value=default_name)
    input_time = st.slider("往復にかかる時間 (分)", min_value=10, max_value=120, value=default_time, step=5)
    
    if st.button("リストに追加", type="primary"):
        if input_loc and selected_loc != "(場所を選択)":
            st.session_state.orders.append({"location": input_loc, "time": input_time})
            st.success(f"「{input_loc}」を追加しました")
        else:
            st.error("場所を選択するか入力してください")

    st.divider()
    
    st.header("⚙️ 体制設定")
    driver_count = st.slider("現在の配達員数", 1, 5, 2)
    
    if st.button("注文リストをクリア"):
        st.session_state.orders = []
        st.rerun()

# --- メインエリア：表示 ---

st.subheader(f"📋 現在の注文スタック ({len(st.session_state.orders)}件)")

if st.session_state.orders:
    # リスト表示 (indexを1から表示)
    df = pd.DataFrame(st.session_state.orders)
    df.columns = ["配達先", "往復時間(分)"]
    df.index = df.index + 1
    st.dataframe(df, use_container_width=True)
    
    # 計算実行
    final_wait, avg_rt, wait_factor, raw_calc = calculate_wait_time(st.session_state.orders, driver_count)
    
    st.divider()
    
    # 結果表示
    st.subheader("⏱️ 計算されたご案内時間")
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.metric(
            label="お客様への案内",
            value=f"{final_wait} 分",
            delta="最低30分保証" if final_wait == 30 and raw_calc < 30 else None,
            delta_color="off"
        )
    
    with col2:
        # 計算式の可視化
        st.info(f"""
        **計算ロジック:**
        $$
        ({avg_rt:.1f}\\text{{分}} \\times \\frac{{{len(st.session_state.orders)-1}\\text{{件}}}}{{{driver_count}\\text{{人}}}}) + {avg_rt/2:.1f}\\text{{分}} = {raw_calc:.1f}\\text{{分}}
        $$
        
        - **平均往復:** {avg_rt:.1f} 分
        - **待ち係数:** {wait_factor:.2f} (前の件数 ÷ 配達員数)
        - **平均片道:** {avg_rt/2:.1f} 分
        """)
        
else:
    st.info("👈 左のサイドバーから注文を追加してください")
    st.metric(label="お客様への案内", value="30 分")