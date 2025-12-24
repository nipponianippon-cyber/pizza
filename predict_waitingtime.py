import streamlit as st
import pandas as pd
import uuid

# ==========================================
# Master
# ==========================================
LOCATION_MASTER = {
    "A": 15,
    "B": 30,
    "C": 40,
    "D": 25,
    "E": 35
}

# ==========================================
# Init Session
# ==========================================
if 'orders' not in st.session_state:
    st.session_state.orders = []

# ==========================================
# Logic
# ==========================================
def calculate_wait_time(orders_list, driver_count):
    if not orders_list:
        return 30, 0, 0, 0
    
    times = [o["time"] for o in orders_list]
    num_orders = len(times)
    
    avg_round_trip = sum(times) / num_orders
    avg_one_way = avg_round_trip / 2
    
    waiting_factor = (num_orders - 1) / driver_count
    raw_time = (avg_round_trip * waiting_factor) + avg_one_way
    
    final_time = max(30, raw_time)
    
    return int(final_time), avg_round_trip, waiting_factor, raw_time

# 注文削除関数
def delete_order(order_id):
    st.session_state.orders = [o for o in st.session_state.orders if o["id"] != order_id]

# ==========================================
# UI
# ==========================================
st.title("")

# --- サイドバー：入力エリア ---
with st.sidebar:
    st.header("注文の追加")
    
    select_options = ["(場所を選択)"] + list(LOCATION_MASTER.keys()) + ["その他"]
    selected_loc = st.selectbox("配達先を選択", select_options)
    
    default_name = ""
    default_time = 30
    if selected_loc in LOCATION_MASTER:
        default_name = selected_loc
        default_time = LOCATION_MASTER[selected_loc]
    elif selected_loc == "その他":
        default_name = ""
        default_time = 30
    
    input_loc = st.text_input("地名・備考", value=default_name)
    input_time = st.slider("往復時間 (分)", min_value=10, max_value=120, value=default_time, step=5)
    
    if st.button("リストに追加", type="primary"):
        if input_loc and selected_loc != "(場所を選択)":
            # IDを付与して追加
            new_order = {
                "id": str(uuid.uuid4()), # ユニークID
                "location": input_loc, 
                "time": input_time
            }
            st.session_state.orders.append(new_order)
            st.success(f"「{input_loc}」を追加")
        else:
            st.error("場所を選択するか入力")

    st.divider()
    
    st.header("設定")
    driver_count = st.slider("現在の配達員数", 1, 5, 2)
    
    if st.button("全件クリア"):
        st.session_state.orders = []
        st.rerun()

# --- メインエリア：表示 ---

st.subheader(f"現在の注文 ({len(st.session_state.orders)}件)")

if st.session_state.orders:
    # --- 修正箇所: 注文リストをループで表示 ---
    # コンテナを作って枠線で囲む
    with st.container(border=True):
        # ヘッダー行
        h1, h2, h3 = st.columns([3, 1.5, 1])
        h1.markdown("**配達先**")
        h2.markdown("**往復時間**")
        h3.markdown("**操作**")
        st.divider()
        
        # 各注文の行
        for i, order in enumerate(st.session_state.orders):
            c1, c2, c3 = st.columns([3, 1.5, 1])
            
            # 場所
            c1.write(f"#{i+1} {order['location']}")
            
            # 時間
            c2.write(f"{order['time']}分")
            
            # 完了ボタン (keyにIDを使うことでボタンを区別)
            if c3.button("完了", key=order["id"]):
                delete_order(order["id"])
                st.rerun() # 画面を再読み込みして反映
    
    # 計算実行
    final_wait, avg_rt, wait_factor, raw_calc = calculate_wait_time(st.session_state.orders, driver_count)
    
    st.divider()
    
    # 結果表示
    st.subheader("予測時間")
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.metric(
            label="",
            value=f"{final_wait} 分",
            delta="30分" if final_wait == 30 and raw_calc < 30 else None,
            delta_color="off"
        )
    
    with col2:
        st.info(f"""
        **内訳:**
        $$
        ({avg_rt:.1f}\\text{{分}} \\times \\frac{{{len(st.session_state.orders)-1}\\text{{件}}}}{{{driver_count}\\text{{人}}}}) + {avg_rt/2:.1f}\\text{{分}} = {raw_calc:.1f}\\text{{分}}
        $$
        
        - **平均往復:** {avg_rt:.1f} 分
        - **係数:** {wait_factor:.2f}
        - **平均片道:** {avg_rt/2:.1f} 分
        """)
        
else:
    st.info("左のサイドバーから注文を追加")
    st.metric(label="", value="30 分")