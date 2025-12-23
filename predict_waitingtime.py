import streamlit as st
import math
import pandas as pd
import datetime
import uuid

# ==========================================
# 1. 設定・マスタデータ
# ==========================================

ZONE_CONFIG = {
    "Zone_A": {"label": "近距離エリア", "dist_km": 1.0},
    "Zone_B": {"label": "中距離エリア", "dist_km": 2.0},
    "Zone_C": {"label": "遠距離エリア", "dist_km": 4.0},
    "Zone_D": {"label": "特遠エリア",   "dist_km": 6.0},
}

LOCATION_MAP = {
    "鹿塩": "Zone_A", "大吹": "Zone_A", "亀井": "Zone_A", "末成": "Zone_A",
    "大成": "Zone_A", "小林": "Zone_A", "光明": "Zone_A", "高司": "Zone_A",
    "段上(1~4)": "Zone_B", "千種": "Zone_B", "仁川": "Zone_B",
    "仁川高台": "Zone_B", "仁川高丸": "Zone_B", "仁川(5~6)": "Zone_C",
    "上ヶ原": "Zone_C", "上甲東園": "Zone_B", "甲東園": "Zone_B",
    "上大市": "Zone_C", "下大市": "Zone_C", "段上(5~8)": "Zone_C",
    "安倉西": "Zone_B", "安倉中": "Zone_B", "西野": "Zone_B",
    "中野西": "Zone_B", "中野北": "Zone_B", "美座": "Zone_C",
    "小浜": "Zone_C", "弥生": "Zone_C", "福井": "Zone_A",
    "末広": "Zone_B", "中州": "Zone_B", "逆瀬川": "Zone_A",
    "南口": "Zone_C", "光が丘": "Zone_C", "青葉台": "Zone_C",
    "寿楽荘": "Zone_C", "長寿が丘": "Zone_D", "月見山": "Zone_D",
    "宝松苑": "Zone_C", "逆瀬台": "Zone_C", "野上(1~3)": "Zone_B",
    "野上(4~6)": "Zone_C"
}

WEATHER_CONFIG = {
    "晴": {"speed": 1.0, "stack": 1.0},
    "雨": {"speed": 0.8, "stack": 0.8},
    "雪": {"speed": 0.5, "stack": 0.5} # 雪も追加
}

# ==========================================
# 2. セッション状態の管理（注文リスト）
# ==========================================
if 'orders' not in st.session_state:
    st.session_state.orders = []

def add_order(type, count, location, note):
    """注文を追加する"""
    st.session_state.orders.append({
        "id": str(uuid.uuid4())[:8],
        "time": datetime.datetime.now().strftime("%H:%M"),
        "type": type,
        "count": count,
        "location": location,
        "note": note,
        "status": "active"
    })

def complete_order(order_id):
    """注文を完了（リストから削除）する"""
    st.session_state.orders = [o for o in st.session_state.orders if o['id'] != order_id]

# ==========================================
# 3. 計算ロジック（バックログ集計版）
# ==========================================

def get_current_backlog():
    """現在の注文リストから負荷を集計する"""
    active_orders = st.session_state.orders
    
    # ピザ総枚数（オーブン負荷）
    total_pizzas = sum([o['count'] for o in active_orders])
    
    # デリバリー件数（ドライバー負荷）
    delivery_queue = len([o for o in active_orders if o['type'] == 'Delivery'])
    
    return total_pizzas, delivery_queue

def predict_wait_time(new_order_type, new_count, location, oven_count, bake_time, prep_time, driver_count, weather):
    """
    現在のバックログ + 新規注文の負荷 で待ち時間を予測する
    """
    # 現在の負荷を取得
    current_pizza_backlog, current_delivery_queue = get_current_backlog()
    
    # --- テイクアウト・オーブン計算 ---
    # オーブンシミュレーション
    ovens = [0.0] * oven_count
    oven_interval = 1.0
    
    # 1. 既存のバックログを埋める
    for _ in range(current_pizza_backlog):
        earliest = ovens.index(min(ovens))
        ovens[earliest] += oven_interval
        
    # 2. 新規注文分を埋める
    # 新規注文の完了時刻を計算
    last_finish = 0.0
    for _ in range(new_count):
        earliest = ovens.index(min(ovens))
        # 準備時間 vs オーブン空き
        entry = max(ovens[earliest], prep_time)
        ovens[earliest] = entry + oven_interval
        last_finish = entry + bake_time
        
    takeout_time = int(last_finish)

    if new_order_type == "Takeout":
        return takeout_time, {}

    # --- デリバリー計算 ---
    if new_order_type == "Delivery":
        zone_id = LOCATION_MAP[location]
        zone_info = ZONE_CONFIG[zone_id]
        dist_km = zone_info["dist_km"]
        w_conf = WEATHER_CONFIG[weather]

        # 能力計算
        per_driver = math.floor(3 * w_conf["stack"])
        if per_driver < 1: per_driver = 1
        fleet_capa = driver_count * per_driver
        
        # 既存待ち + 今回の1件
        rounds = math.ceil((current_delivery_queue + 1) / fleet_capa)
        
        round_trip = 30 / w_conf["speed"]
        wait_time = max(0, (rounds - 1) * round_trip)
        
        speed = 40.0 * w_conf["speed"]
        travel = (dist_km / speed) * 60
        
        delivery_total = int(prep_time + wait_time + travel)
        
        return delivery_total, {
            "wait": int(wait_time),
            "travel": int(travel),
            "zone": zone_info["label"]
        }

# ==========================================
# 4. UI構築（店舗管理画面）
# ==========================================

st.set_page_config(page_title="Pizza Manager", layout="wide")

st.title("🍕 店舗運営・注文管理ダッシュボード")

# サイドバー：環境設定
with st.sidebar:
    st.header("店舗環境設定")
    st.markdown("※シフト変更時などに更新")
    weather = st.radio("現在の天候", ["晴", "雨", "雪"], horizontal=True)
    driver_count = st.slider("稼働ドライバー", 1, 10, 3)
    oven_count = st.slider("稼働オーブン", 1, 5, 2)
    
    st.divider()
    st.subheader("基本パラメータ")
    prep_time = st.number_input("調理準備(分)", 5, 60, 15)
    bake_time = st.number_input("焼成時間(分)", 3.0, 15.0, 6.5)

# 現在の負荷状況表示
curr_pizzas, curr_delivs = get_current_backlog()
col1, col2, col3 = st.columns(3)
col1.metric("未提供ピザ総数", f"{curr_pizzas} 枚", "オーブン待ち含む")
col2.metric("未完了デリバリー", f"{curr_delivs} 件", "配送待ち含む")
col3.metric("現在の天候係数", f"速度 {WEATHER_CONFIG[weather]['speed']}倍")

st.divider()

# レイアウト：左側（新規注文・見積もり） / 右側（注文管理リスト）
left_col, right_col = st.columns([1, 1.5])

# === 左側：新規注文入力＆見積もり ===
with left_col:
    st.subheader("📞 新規注文受付 / 時間案内")
    
    with st.container(border=True):
        input_type = st.radio("注文タイプ", ["Takeout", "Delivery"], horizontal=True)
        
        c1, c2 = st.columns(2)
        input_count = c1.number_input("枚数", 1, 20, 1)
        input_note = c2.text_input("顧客名/メモ", "様")
        
        input_loc = "鹿塩" # デフォルト
        if input_type == "Delivery":
            input_loc = st.selectbox("お届け先", list(LOCATION_MAP.keys()))
        
        # リアルタイム予測計算
        pred_time, details = predict_wait_time(
            input_type, input_count, input_loc, 
            oven_count, bake_time, prep_time, driver_count, weather
        )
        
        st.markdown("### 案内予測時間")
        if input_type == "Takeout":
            st.metric("お渡しまで", f"{pred_time} 分")
        else:
            st.metric("お届けまで", f"{pred_time} 分")
            st.caption(f"内訳: 調理{prep_time} + 配車待ち{details.get('wait')} + 移動{details.get('travel')}")

        # 確定ボタン
        if st.button("注文を確定・リスト追加", type="primary", use_container_width=True):
            add_order(input_type, input_count, input_loc, input_note)
            st.success("注文リストに追加しました！待ち時間が更新されます。")
            st.rerun()

# === 右側：現在の注文リスト ===
with right_col:
    st.subheader("📋 現在進行中のオーダー")
    
    if not st.session_state.orders:
        st.info("現在、未処理のオーダーはありません。")
    else:
        # データフレームで見やすく表示
        df = pd.DataFrame(st.session_state.orders)
        
        # カード形式で表示して、完了ボタンを配置
        for i, order in enumerate(st.session_state.orders):
            with st.expander(f"#{i+1} {order['time']} 受付: {order['note']} ({order['type']})"):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{order['count']}枚**")
                if order['type'] == 'Delivery':
                    c2.write(f"📍 {order['location']}")
                else:
                    c2.write("🥡 店頭受取")
                
                if c3.button("完了", key=f"btn_{order['id']}"):
                    complete_order(order['id'])
                    st.rerun()