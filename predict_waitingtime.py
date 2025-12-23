import streamlit as st
import math
import pandas as pd
import datetime
from datetime import timedelta
import uuid

# ==========================================
# 1. 設定・マスタデータ (距離を個別に設定)
# ==========================================

# 距離マスタ（住所ごとの距離を定義）
# zoneは天候係数の参照用、dist_kmは実際の移動計算用
LOCATION_DETAILS = {
    # Zone_A (約1km圏内)
    "鹿塩": {"zone": "Zone_A", "dist": 0.8},
    "大吹": {"zone": "Zone_A", "dist": 1.1},
    "亀井": {"zone": "Zone_A", "dist": 1.2},
    "末成": {"zone": "Zone_A", "dist": 1.5},
    "大成": {"zone": "Zone_A", "dist": 0.9},
    "小林": {"zone": "Zone_A", "dist": 1.3},
    "光明": {"zone": "Zone_A", "dist": 1.4},
    "高司": {"zone": "Zone_A", "dist": 1.0},
    "福井": {"zone": "Zone_A", "dist": 1.5},
    "逆瀬川": {"zone": "Zone_A", "dist": 1.2},
    
    # Zone_B (約2km圏内)
    "段上(1~4)": {"zone": "Zone_B", "dist": 2.1},
    "千種": {"zone": "Zone_B", "dist": 2.3},
    "仁川": {"zone": "Zone_B", "dist": 2.5},
    "仁川高台": {"zone": "Zone_B", "dist": 1.3},
    "仁川高丸": {"zone": "Zone_B", "dist": 1.6},
    "上甲東園": {"zone": "Zone_B", "dist": 2.2},
    "甲東園": {"zone": "Zone_B", "dist": 2.4},
    "安倉西": {"zone": "Zone_B", "dist": 1.6},
    "安倉中": {"zone": "Zone_B", "dist": 2.6},
    "西野": {"zone": "Zone_B", "dist": 1.5},
    "中野西": {"zone": "Zone_B", "dist": 2.4},
    "中野北": {"zone": "Zone_B", "dist": 2.3},
    "末広": {"zone": "Zone_B", "dist": 1.6},
    "中州": {"zone": "Zone_B", "dist": 1.8},
    "野上(1~3)": {"zone": "Zone_B", "dist": 2.0},

    # Zone_C (約4km圏内)
    "仁川(5~6)": {"zone": "Zone_C", "dist": 2.2},
    "上ヶ原": {"zone": "Zone_C", "dist": 3.0},
    "上大市": {"zone": "Zone_C", "dist": 2.9},
    "下大市": {"zone": "Zone_C", "dist": 3.5},
    "段上(5~8)": {"zone": "Zone_C", "dist": 2.5},
    "美座": {"zone": "Zone_C", "dist": 2.1},
    "小浜": {"zone": "Zone_C", "dist": 3.5},
    "弥生": {"zone": "Zone_C", "dist": 2.4},
    "南口": {"zone": "Zone_C", "dist": 2.5},
    "光が丘": {"zone": "Zone_C", "dist": 3.3},
    "青葉台": {"zone": "Zone_C", "dist": 3.3},
    "寿楽荘": {"zone": "Zone_C", "dist": 2.6},
    "宝松苑": {"zone": "Zone_C", "dist": 2.6},
    "逆瀬台": {"zone": "Zone_C", "dist": 3.0},
    "野上(4~6)": {"zone": "Zone_C", "dist": 3.5},

    # Zone_D (遠方)
    "長寿が丘": {"zone": "Zone_D", "dist": 4.4},
    "月見山": {"zone": "Zone_D", "dist": 4.2},
}

WEATHER_CONFIG = {
    "晴": {"speed": 1.0, "stack": 1.0},
    "雨": {"speed": 0.8, "stack": 0.8}
}

# ==========================================
# セッション状態管理
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
# 積み上げ計算ロジック（滞在時間考慮版）
# ==========================================
def calculate_stack_schedule(new_orders_list, oven_count, bake_time, prep_time, driver_count_func, weather):
    """
    注文を「時間順」に並べ替え、前から順番にオーブンに詰め込んでいく（スタック方式）
    driver_count_func: 時刻を渡すとその時間のドライバー数を返す関数
    """
    current_time = get_current_time()
    w_conf = WEATHER_CONFIG[weather]
    
    # ★設定：配達先での平均滞在時間（分）
    DELIVERY_STAY_MIN = 4.0
    
    # ====================================================
    # 1. 現在の注文状況から「平均1回転時間（サイクル）」を動的計算
    # ====================================================
    
    active_deliveries = [o for o in st.session_state.orders if o['type'] == 'Delivery']
    
    if active_deliveries:
        total_round_trip_min = 0
        current_speed = 17.25 * w_conf["speed"]
        
        for o in active_deliveries:
            loc_key = o['location']
            dist = 1.0
            if loc_key in LOCATION_DETAILS:
                dist = LOCATION_DETAILS[loc_key]['dist']
            
            # 片道移動時間
            one_way_min = (dist / current_speed) * 60
            
            # ★修正箇所：往復時間 = (片道 * 2) + 現地滞在時間(4分)
            round_trip_min = (one_way_min * 2) + DELIVERY_STAY_MIN
            
            total_round_trip_min += round_trip_min
            
        avg_cycle_time = total_round_trip_min / len(active_deliveries)
        # 最低保証（近場でも15分+4分はかかる想定）
        avg_cycle_time = max(19.0, avg_cycle_time)
        
    else:
        # デリバリー注文がない場合：デフォルト30分 + 滞在4分
        avg_cycle_time = 30.0 + DELIVERY_STAY_MIN

    # ====================================================

    # 2. 全タスクのリスト化
    all_tasks = []
    for o in st.session_state.orders:
        all_tasks.append({**o, "is_new": False})
    for new_o in new_orders_list:
        sim_created = new_o.get('target_time') if new_o['is_reservation'] else current_time
        all_tasks.append({**new_o, "created_at": sim_created, "is_new": True})

    # 3. 並び順の決定
    calc_tasks = []
    prep_delta = timedelta(minutes=prep_time)
    for t in all_tasks:
        if t['is_reservation']:
            start_base = t['target_time'] - timedelta(minutes=30)
            priority_time = max(start_base, current_time)
        else:
            priority_time = t['created_at']
        calc_tasks.append({**t, "priority_time": priority_time})
    
    calc_tasks.sort(key=lambda x: x['priority_time'])

    # 4. オーブンの積み上げ計算
    ovens = [current_time] * oven_count
    oven_interval = timedelta(minutes=1) 
    bake_duration = timedelta(minutes=bake_time)

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

    # 5. 結果の返却
    target_result = simulation_results.get('SIMULATION')
    if not target_result:
        return None, None

    # デリバリー計算
    delivery_details = {}
    total_finish_time = target_result
    
    target_new = new_orders_list[0]

    if target_new['type'] == "Delivery":
        loc_key = target_new['location']
        if loc_key in LOCATION_DETAILS:
            dist_km = LOCATION_DETAILS[loc_key]['dist']
        else:
            dist_km = 1.0 

        speed = 17.25 * w_conf["speed"]
        travel_min = (dist_km / speed) * 60
        
        # ドライバー数と能力
        current_drivers = driver_count_func(total_finish_time)
        per_driver = math.floor(1 * w_conf["stack"])
        if per_driver < 1: per_driver = 1
        fleet_capa = current_drivers * per_driver
        if fleet_capa < 1: fleet_capa = 1 

        # 配車待ち
        prior_deliveries = len([t for t in calc_tasks 
                                if t['type'] == 'Delivery' 
                                and t['priority_time'] <= target_new.get('priority_time', current_time)
                                and not t.get('is_new')])
        
        # ★ここで「滞在時間込みのサイクルタイム」を使って待ち時間を計算
        unit_wait = avg_cycle_time / fleet_capa
        wait_min = prior_deliveries * unit_wait
        
        # ※お客様への到着時間には「自分の分の滞在時間」は足さない（到着＝ドア前）のが一般的ですが、
        # もし「受け渡し完了時間」まで含めるなら travel_min に +4 してください。
        # ここでは「到着時刻」として移動時間のみを足します。
        total_finish_time += timedelta(minutes=wait_min + travel_min)
        
        delivery_details = {
            "baked": target_result.strftime("%H:%M"),
            "wait": int(wait_min),
            "travel": int(travel_min),
            "drivers": current_drivers,
            "avg_cycle": int(avg_cycle_time)
        }

    return total_finish_time, delivery_details

# ==========================================
# UI構築
# ==========================================

st.set_page_config(page_title="Pizza Wait Time Pro", layout="wide")
st.title("")

# --- サイドバー設定（ドライバーシフト表） ---
with st.sidebar:
    st.header("環境設定")
    weather = st.radio("天候", ["晴", "雨"], horizontal=True)
    oven_count = st.slider("オーブン数", 1, 5, 2)
    prep_time = st.number_input("準備時間(分)", 5, 60, 15)
    bake_time = st.number_input("焼成時間(分)", 3.0, 15.0, 6.5)
    
    st.divider()
    st.subheader("配達員")
    
    # デフォルトのシフトデータ
    default_schedule = pd.DataFrame({
        "Hour": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
        "Drivers": [2, 3, 3, 2, 2, 2, 3, 4, 4, 3, 2, 1]
    })
    
    # データエディタで編集可能にする
    edited_schedule = st.data_editor(
        default_schedule, 
        column_config={"Hour": st.column_config.NumberColumn(format="%d時")},
        hide_index=True,
        use_container_width=True
    )
    
    # ドライバー数取得関数の作成
    def get_drivers_at_hour(dt_or_hour):
        if isinstance(dt_or_hour, datetime.datetime):
            h = dt_or_hour.hour
        else:
            h = int(dt_or_hour)
        
        # 時間外は最小1人とする
        if h < 11 or h > 22:
            return 1
            
        row = edited_schedule[edited_schedule["Hour"] == h]
        if not row.empty:
            return int(row.iloc[0]["Drivers"])
        return 1
    
    # サイドバーの最後に追加
    st.divider()
    st.markdown("**現在の配送ペース**")
    
    # 実際の計算ロジックと同じ計算をして表示
    active_dels = [o for o in st.session_state.orders if o['type'] == 'Delivery']
    if active_dels:
        total_mins = 0
        w_speed = 17.25 * WEATHER_CONFIG[weather]["speed"]
        
        for o in active_dels:
            d = LOCATION_DETAILS.get(o['location'], {"dist":1.0})['dist']
            
            # ★修正: 往復時間(移動) + 滞在時間(4分)
            one_way = (d / w_speed) * 60
            round_trip = (one_way * 2) + 4.0 
            
            total_mins += round_trip
            
        avg_pac = int(total_mins / len(active_dels))
        
        # 最低保証も 15+4=19分 くらいに合わせるとベターです
        st.caption(f"平均往復時間: 約 {max(19, avg_pac)} 分 / 件")
        st.caption(f"{len(active_dels)} 件の平均")
    else:
        # デフォルト表示も合わせる
        st.caption("平均往復時間: 30分 (デフォルト)")

# --- (iii) 未来の時間帯別 待ち時間予測ボード ---
st.markdown("### 予測待ち時間")

# 現在時刻を取得
current_h = get_current_time().hour

# スライダーのデフォルト値を計算（現在〜5時間後、ただし範囲内に収める）
default_start = max(11, current_h)
default_end = min(22, default_start + 5)

# 1. 範囲選択スライダー
selected_range = st.slider(
    "",
    min_value=11, 
    max_value=22, 
    value=(default_start, default_end), # (開始, 終了) の初期値
    format="%d時"
)

start_view, end_view = selected_range

# 2. 選択された範囲でループ表示
# カラム数は6つ（6時間を超える範囲を選択した場合は、次の行に折り返されます）
cols = st.columns(6)

count = 0
for h in range(start_view, end_view + 1):
    # その時間の仮注文データを作成
    target_dt = get_current_time().replace(hour=h, minute=0)
    
    # 過去の時間を選んだ場合は、現在時刻として計算（過去の予測はできないため）
    if target_dt < get_current_time():
        target_dt = get_current_time()

    dummy_del = {
        "type": "Delivery", "count": 1, "location": "鹿塩", # 標準距離
        "target_time": target_dt, "is_reservation": True
    }
    
    fin_dt, dets = calculate_stack_schedule(
        [dummy_del], oven_count, bake_time, prep_time, get_drivers_at_hour, weather
    )
    
    # 待ち時間（分）
    wait_m = math.ceil((fin_dt - target_dt).total_seconds() / 60)
    disp_wait = max(30, wait_m) # 最低保証30分
    
    # その時間のドライバー数
    d_num = get_drivers_at_hour(h)
    
    # 状況に応じた色文字（Streamlitのmetricは色変更できないため、delta機能で簡易表現）
    # 混雑度合いを視覚化
    delta_color = "normal"
    if disp_wait > 60: delta_color = "inverse" # 赤っぽく目立たせる意図
    
    # 表示（6列で折り返し）
    with cols[count % 6]:
        st.metric(
            label=f"{h}:00", 
            value=f"{disp_wait}min", 
            delta=f"{d_num}人",
            delta_color=delta_color
        )
    count += 1


st.divider()

# --- 通常の注文入力画面 ---

col_main, col_list = st.columns([1.2, 1.5])

with col_main:
    st.subheader("新規注文入力")
    
    with st.container(border=True):
        order_mode = st.radio("受付タイプ", ["今すぐ", "予約"], horizontal=True)
        
        target_dt = get_current_time()
        
        if order_mode == "予約":
            col_t1, col_t2 = st.columns(2)
            res_date = col_t1.date_input("日付", datetime.date.today())
            res_time = col_t2.time_input("希望時刻", (get_current_time() + timedelta(minutes=60)).time())
            target_dt = datetime.datetime.combine(res_date, res_time)
        
        order_type = st.selectbox("受取方法", ["Takeout", "Delivery"])
        
        c1, c2 = st.columns(2)
        count = c1.number_input("枚数", 1, 20, 1)
        loc = "鹿塩"
        
        dist_display = ""
        if order_type == "Delivery":
            # (i) 個別距離の選択肢
            loc = c2.selectbox("お届け先", list(LOCATION_DETAILS.keys()))
            dist_val = LOCATION_DETAILS[loc]['dist']
            dist_display = f"({dist_val}km)"
        else:
            note = c2.text_input("顧客名/メモ", "様")

        # --- 個別シミュレーション ---
        sim_order = {
            "type": order_type, 
            "count": count, 
            "location": loc, 
            "target_time": target_dt, 
            "is_reservation": (order_mode == "予約")
        }
        
        finish_dt, details = calculate_stack_schedule(
            [sim_order], oven_count, bake_time, prep_time, get_drivers_at_hour, weather
        )
        
        # 待ち時間表示
        wait_min_actual = int((finish_dt - target_dt).total_seconds()/60)
        
        st.markdown(f"**完了予定:** `{finish_dt.strftime('%H:%M')}` {dist_display}")
        
        if order_mode == "予約":
            if finish_dt <= target_dt:
                st.success(f"予約OK (余裕 {abs(wait_min_actual)}分)")
            else:
                st.error(f"遅延見込み (+{wait_min_actual}分)")
        else:
            # 今すぐの場合
            st.info(f"予想待ち時間: 約 {max(0, wait_min_actual)} 分")

        if st.button("Add Order", type="primary", use_container_width=True):
            add_order(order_type, count, loc, 
                      note if order_type=="Takeout" else f"配送: {loc}", 
                      target_dt, (order_mode == "予約"))
            st.success("注文を追加しました")
            st.rerun()

with col_list:
    st.subheader("現在の注文")
    
    if st.session_state.orders:
        orders = st.session_state.orders
        total_pizzas = sum(o['count'] for o in orders)
        st.caption(f"待機: {len(orders)}件 / ピザ残: {total_pizzas}枚")
        
        # 表示用にソート
        display_list = []
        for o in orders:
            p_time = o['created_at']
            if o['is_reservation']:
                p_time = max(o['target_time'] - timedelta(minutes=30), get_current_time())
            display_list.append({**o, "sort_key": p_time})
            
        display_list.sort(key=lambda x: x['sort_key'])
        
        for o in display_list:
            icon = "📅" if o['is_reservation'] else "⚡"
            time_str = o['target_time'].strftime('%H:%M') if o['is_reservation'] else o['created_at'].strftime('%H:%M')
            
            with st.expander(f"{icon} {time_str} | {o['count']}枚 ({o['type']})"):
                st.write(f"内容: {o['note'] if o['type']=='Takeout' else o['location']}")
                if st.button("完了", key=o['id']):
                    complete_order(o['id'])
                    st.rerun()
    else:
        st.info("No Active Orders")