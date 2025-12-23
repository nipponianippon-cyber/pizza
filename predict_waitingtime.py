import streamlit as st
import math
import pandas as pd
import datetime
from datetime import timedelta
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
    "雪": {"speed": 0.5, "stack": 0.5}
}

# ==========================================
# 2. セッション状態管理
# ==========================================
if 'orders' not in st.session_state:
    st.session_state.orders = []

def get_current_time():
    """現在時刻を取得（秒以下切り捨て）"""
    return datetime.datetime.now().replace(second=0, microsecond=0)

def add_order(type, count, location, note, target_time_dt, is_reservation):
    """注文をスタックに追加"""
    st.session_state.orders.append({
        "id": str(uuid.uuid4())[:8],
        "created_at": get_current_time(),
        "target_time": target_time_dt, 
        "is_reservation": is_reservation,
        "type": type,
        "count": count,
        "location": location,
        "note": note,
        "status": "active"
    })

def complete_order(order_id):
    st.session_state.orders = [o for o in st.session_state.orders if o['id'] != order_id]

# ==========================================
# 3. 積み上げ計算ロジック（予約考慮版）
# ==========================================

def calculate_stack_schedule(new_orders_list, oven_count, bake_time, prep_time, driver_count, weather):
    """
    注文を「時間順」に並べ替え、前から順番にオーブンに詰め込んでいく（スタック方式）
    """
    current_time = get_current_time()
    
    # 1. 全タスクのリスト化（既存 + 新規シミュレーション用）
    all_tasks = []
    
    # 既存オーダー
    for o in st.session_state.orders:
        all_tasks.append({**o, "is_new": False})
        
    # 新規シミュレーション用オーダー
    for new_o in new_orders_list:
        all_tasks.append({**new_o, "created_at": current_time, "is_new": True})

    # 2. 並び順の決定
    calc_tasks = []
    prep_delta = timedelta(minutes=prep_time)
    
    for t in all_tasks:
        if t['is_reservation']:
            # 予約：希望時刻の30分前基準
            start_base = t['target_time'] - timedelta(minutes=30)
            priority_time = max(start_base, current_time)
        else:
            # 今すぐ：受注時刻基準
            priority_time = t['created_at']
            
        calc_tasks.append({
            **t,
            "priority_time": priority_time
        })
    
    # 時間順にソート（予約が割り込む形になる）
    calc_tasks.sort(key=lambda x: x['priority_time'])

    # 3. オーブンの積み上げ計算
    ovens = [current_time] * oven_count
    oven_interval = timedelta(minutes=1) 
    bake_duration = timedelta(minutes=bake_time)

    # 結果格納用
    simulation_results = {}

    for task in calc_tasks:
        task_finish_time = current_time 
        
        for _ in range(task['count']):
            earliest_idx = ovens.index(min(ovens))
            oven_ready_time = ovens[earliest_idx]
            
            entry_time = max(oven_ready_time, task['priority_time'] + prep_delta)
            
            ovens[earliest_idx] = entry_time + oven_interval
            
            finish_time = entry_time + bake_duration
            task_finish_time = max(task_finish_time, finish_time)
            
        simulation_results[task.get('id', 'SIMULATION')] = task_finish_time

    # 4. 結果の返却（新規注文分のみ）
    target_result = simulation_results.get('SIMULATION')
    
    if not target_result:
        return None, None

    # デリバリー計算（簡易版）
    delivery_details = {}
    total_finish_time = target_result
    
    target_new = new_orders_list[0]

    if target_new['type'] == "Delivery":
        w_conf = WEATHER_CONFIG[weather]
        # デリバリーの場合、指定場所までの距離計算
        # ※案内時間計算時は、標準的な場所（Zone_Aなど）を使用する想定
        loc_key = target_new['location']
        if loc_key in LOCATION_MAP:
            zone_id = LOCATION_MAP[loc_key]
            dist_km = ZONE_CONFIG[zone_id]['dist_km']
        else:
            dist_km = 1.0 # デフォルト

        speed = 40.0 * w_conf["speed"]
        travel_min = (dist_km / speed) * 60
        
        # 配車待ち
        prior_deliveries = len([t for t in calc_tasks 
                                if t['type'] == 'Delivery' 
                                and t['priority_time'] <= target_new.get('priority_time', current_time)
                                and not t.get('is_new')])
        
        wait_min = prior_deliveries * 5 
        
        total_finish_time += timedelta(minutes=wait_min + travel_min)
        
        delivery_details = {
            "baked": target_result.strftime("%H:%M"),
            "wait": int(wait_min),
            "travel": int(travel_min)
        }

    return total_finish_time, delivery_details

# ==========================================
# 4. UI構築
# ==========================================

st.set_page_config(page_title="Pizza Wait Time", layout="wide")
st.title("🍕 Pizza Stack Manager")

# サイドバー設定
with st.sidebar:
    st.header("環境設定")
    weather = st.radio("天候", ["晴", "雨", "雪"], horizontal=True)
    driver_count = st.slider("ドライバー数", 1, 10, 3)
    oven_count = st.slider("オーブン数", 1, 5, 2)
    st.divider()
    prep_time = st.number_input("準備時間(分)", 5, 60, 15)
    bake_time = st.number_input("焼成時間(分)", 3.0, 15.0, 6.5)

# --- 【追加ロジック】現在の客向け案内時間の計算 ---
current_dt = get_current_time()

# 1. 仮想テイクアウト注文（1枚）でシミュレーション
dummy_takeout = {
    "type": "Takeout", "count": 1, "location": "", 
    "target_time": current_dt, "is_reservation": False
}
to_finish, _ = calculate_stack_schedule(
    [dummy_takeout], oven_count, bake_time, prep_time, driver_count, weather
)
# 現在時刻との差分（分）
to_wait_min = math.ceil((to_finish - current_dt).total_seconds() / 60)
# ★デフォルト15分未満なら15分にする
announce_to = max(15, to_wait_min)

# 2. 仮想デリバリー注文（1枚・標準エリア鹿塩）でシミュレーション
dummy_delivery = {
    "type": "Delivery", "count": 1, "location": "鹿塩", 
    "target_time": current_dt, "is_reservation": False
}
del_finish, _ = calculate_stack_schedule(
    [dummy_delivery], oven_count, bake_time, prep_time, driver_count, weather
)
del_wait_min = math.ceil((del_finish - current_dt).total_seconds() / 60)
# ★デフォルト30分未満なら30分にする
announce_del = max(30, del_wait_min)


# --- 案内表示エリア（最上部） ---
st.markdown("### 📢 現在のお客様へのご案内時間")
# 目立つように表示
metric_col1, metric_col2, metric_col3 = st.columns([1, 1, 2])
with metric_col1:
    st.container(border=True).metric("🥡 テイクアウト", f"{announce_to} 分", help=f"計算値: {to_wait_min}分 / 最低保証: 15分")
with metric_col2:
    st.container(border=True).metric("🛵 デリバリー", f"{announce_del} 分前後", help=f"計算値: {del_wait_min}分 / 最低保証: 30分")
with metric_col3:
    st.info("※上記はピザ1枚の標準的な待ち時間です。\nスタック状況により自動変動します。")

st.divider()

# --- 以降、通常の注文入力画面 ---

col_main, col_list = st.columns([1.2, 1.5])

with col_main:
    st.subheader("📞 新規注文入力")
    
    with st.container(border=True):
        order_mode = st.radio("受付タイプ", ["今すぐ注文", "予約注文"], horizontal=True)
        
        target_dt = current_dt
        
        if order_mode == "予約注文":
            col_t1, col_t2 = st.columns(2)
            res_date = col_t1.date_input("日付", datetime.date.today())
            res_time = col_t2.time_input("希望時刻", (current_dt + timedelta(minutes=60)).time())
            target_dt = datetime.datetime.combine(res_date, res_time)
        
        order_type = st.selectbox("受取方法", ["Takeout", "Delivery"])
        
        c1, c2 = st.columns(2)
        count = c1.number_input("枚数", 1, 20, 1)
        loc = "鹿塩"
        if order_type == "Delivery":
            loc = c2.selectbox("お届け先", list(LOCATION_MAP.keys()))
        else:
            note = c2.text_input("顧客名/メモ", "様")

        # --- 個別注文のシミュレーション（確認用） ---
        sim_order = {
            "type": order_type, 
            "count": count, 
            "location": loc, 
            "target_time": target_dt, 
            "is_reservation": (order_mode == "予約注文")
        }
        
        finish_dt, details = calculate_stack_schedule(
            [sim_order], oven_count, bake_time, prep_time, driver_count, weather
        )
        
        # 個別見積もりの表示
        st.markdown(f"**この注文の完了予定:** `{finish_dt.strftime('%H:%M')}`")
        
        if order_mode == "予約注文":
            if finish_dt <= target_dt:
                st.success("予約時刻に対し、間に合います。")
            else:
                st.error("⚠️ 予約時刻に対し遅延が発生する可能性があります。")

        if st.button("注文を追加（スタック）", type="primary", use_container_width=True):
            add_order(order_type, count, loc, 
                      note if order_type=="Takeout" else f"配送: {loc}", 
                      target_dt, (order_mode == "予約注文"))
            st.success("注文をスタックに追加しました")
            st.rerun()

with col_list:
    st.subheader("📋 スタックされたオーダー")
    
    if st.session_state.orders:
        orders = st.session_state.orders
        total_pizzas = sum(o['count'] for o in orders)
        st.caption(f"待機注文: {len(orders)}件 / バックログ残枚数: {total_pizzas}枚")
        
        # 表示用にソート
        display_list = []
        for o in orders:
            p_time = o['created_at']
            if o['is_reservation']:
                p_time = max(o['target_time'] - timedelta(minutes=30), current_dt)
            display_list.append({**o, "sort_key": p_time})
            
        display_list.sort(key=lambda x: x['sort_key'])
        
        for o in display_list:
            icon = "📅" if o['is_reservation'] else "⚡"
            time_str = o['target_time'].strftime('%H:%M') if o['is_reservation'] else o['created_at'].strftime('%H:%M')
            
            with st.expander(f"{icon} {time_str} | {o['count']}枚 ({o['type']})"):
                st.write(f"内容: {o['note'] if o['type']=='Takeout' else o['location']}")
                if st.button("完了・消込", key=o['id']):
                    complete_order(o['id'])
                    st.rerun()
    else:
        st.info("現在オーダーはありません。")