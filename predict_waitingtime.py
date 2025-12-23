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

    # 2. 並び順の決定（ここが重要）
    # ルール: 
    # - 予約注文は「調理開始希望時刻（ターゲット - 準備時間）」を基準にする
    # - 今すぐ注文は「受注時刻（現在）」を基準にする
    # これらを混ぜて、時間が早い順にソートする
    
    calc_tasks = []
    prep_delta = timedelta(minutes=prep_time)
    
    for t in all_tasks:
        if t['is_reservation']:
            # 予約：希望時刻の30分前には焼き始めたい（余裕枠）
            # ただし、過去の場合は現在時刻にする
            start_base = t['target_time'] - timedelta(minutes=30)
            priority_time = max(start_base, current_time)
        else:
            # 今すぐ：受注時刻（現在）
            priority_time = t['created_at']
            
        calc_tasks.append({
            **t,
            "priority_time": priority_time
        })
    
    # 時間順にソート（予約が割り込む形になる）
    calc_tasks.sort(key=lambda x: x['priority_time'])

    # 3. オーブンの積み上げ計算
    # 各オーブンが「いつ空くか」を持つリスト
    ovens = [current_time] * oven_count
    oven_interval = timedelta(minutes=1) # 投入間隔
    bake_duration = timedelta(minutes=bake_time)

    # 結果格納用
    simulation_results = {}

    for task in calc_tasks:
        task_finish_time = current_time # 初期化
        
        # ピザ枚数分ループ
        for _ in range(task['count']):
            # 一番早く空くオーブンを探す
            earliest_idx = ovens.index(min(ovens))
            oven_ready_time = ovens[earliest_idx]
            
            # 投入時刻の決定
            # 「オーブンの空き」と「その注文の着手可能時刻(priority_time + 準備)」の遅い方
            # これにより、予約時間までオーブンを「空けて待つ」挙動や、
            # 予約の前に隙間があれば「今すぐ注文」をねじ込む挙動が自動計算される
            
            entry_time = max(oven_ready_time, task['priority_time'] + prep_delta)
            
            # オーブン予定更新
            ovens[earliest_idx] = entry_time + oven_interval
            
            # 焼き上がり時刻
            finish_time = entry_time + bake_duration
            task_finish_time = max(task_finish_time, finish_time)
            
        simulation_results[task.get('id', 'SIMULATION')] = task_finish_time

    # 4. 結果の返却（新規注文分のみ）
    # 新規注文が複数ある場合は「最後の注文」の結果を返す仕様とする
    target_result = simulation_results.get('SIMULATION')
    
    if not target_result:
        # 新規注文がない場合（リスト表示用など）はNone
        return None, None

    # デリバリー計算（簡易版）
    delivery_details = {}
    total_finish_time = target_result
    
    # 今回計算対象の新規オーダー情報
    target_new = new_orders_list[0]

    if target_new['type'] == "Delivery":
        w_conf = WEATHER_CONFIG[weather]
        zone_id = LOCATION_MAP[target_new['location']]
        dist_km = ZONE_CONFIG[zone_id]['dist_km']
        
        # 移動
        speed = 40.0 * w_conf["speed"]
        travel_min = (dist_km / speed) * 60
        
        # 配車待ち（簡易スタック計算）
        # 「自分より前にいるデリバリー注文」の数 × 5分
        prior_deliveries = len([t for t in calc_tasks 
                                if t['type'] == 'Delivery' 
                                and t['priority_time'] <= target_new.get('priority_time', current_time)
                                and not t.get('is_new')])
        
        wait_min = prior_deliveries * 5 # 係数
        
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

st.set_page_config(page_title="Pizza Stack Manager", layout="wide")
st.title("🍕 Pizza Stack Manager (積み上げ計算版)")

# サイドバー設定
with st.sidebar:
    st.header("環境設定")
    weather = st.radio("天候", ["晴", "雨", "雪"], horizontal=True)
    driver_count = st.slider("ドライバー数", 1, 10, 3)
    oven_count = st.slider("オーブン数", 1, 5, 2)
    st.divider()
    prep_time = st.number_input("準備時間(分)", 5, 60, 15)
    bake_time = st.number_input("焼成時間(分)", 3.0, 15.0, 6.5)

# メインレイアウト
col_main, col_list = st.columns([1.2, 1.5])

with col_main:
    st.subheader("📞 注文入力")
    
    with st.container(border=True):
        order_mode = st.radio("受付タイプ", ["今すぐ注文", "予約注文"], horizontal=True)
        
        current_dt = get_current_time()
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

        # --- スタック計算実行 ---
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

        st.divider()
        st.markdown("##### 🕒 計算結果")
        
        diff_min = int((finish_dt - current_dt).total_seconds() / 60)
        
        if order_mode == "今すぐ注文":
            st.metric("提供可能時刻", f"{finish_dt.strftime('%H:%M')}", f"待ち時間: 約{diff_min}分")
        else:
            # 予約判定
            if finish_dt <= target_dt:
                st.success(f"✅ 予約OK (完了予定: {finish_dt.strftime('%H:%M')})")
            else:
                delay = int((finish_dt - target_dt).total_seconds()/60)
                st.error(f"⚠️ 予約時刻に間に合いません ({delay}分遅延)")
                st.metric("最短提供", f"{finish_dt.strftime('%H:%M')}")
        
        if details:
             st.caption(f"内訳: 焼き上がり{details['baked']} + 配車待ち{details['wait']}分 + 移動{details['travel']}分")

        if st.button("注文を追加（スタック）", type="primary", use_container_width=True):
            add_order(order_type, count, loc, 
                      note if order_type=="Takeout" else f"配送: {loc}", 
                      target_dt, (order_mode == "予約注文"))
            st.success("注文をスタックに追加しました")
            st.rerun()

    # --- 簡易混雑状況 ---
    st.subheader("📊 現在のバックログ")
    orders = st.session_state.orders
    total_pizzas = sum(o['count'] for o in orders)
    st.info(f"待機中の注文: {len(orders)}件 / ピザ残数: {total_pizzas}枚")

with col_list:
    st.subheader("📋 スタックされたオーダー")
    if st.session_state.orders:
        # 時間順（優先度順）に並べ替えて表示
        # 簡易的にpriority_timeを再計算してソート
        display_list = []
        for o in st.session_state.orders:
            p_time = o['created_at']
            if o['is_reservation']:
                p_time = max(o['target_time'] - timedelta(minutes=30), get_current_time())
            display_list.append({**o, "sort_key": p_time})
            
        display_list.sort(key=lambda x: x['sort_key'])
        
        for o in display_list:
            icon = "📅" if o['is_reservation'] else "⚡"
            time_str = o['target_time'].strftime('%H:%M') if o['is_reservation'] else o['created_at'].strftime('%H:%M')
            
            with st.expander(f"{icon} {time_str} | {o['count']}枚 ({o['type']})"):
                st.write(f"メモ/場所: {o['note'] if o['type']=='Takeout' else o['location']}")
                if st.button("完了・消込", key=o['id']):
                    complete_order(o['id'])
                    st.rerun()
    else:
        st.write("現在オーダーはありません")