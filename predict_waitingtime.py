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
# 2. セッション状態管理（時刻対応版）
# ==========================================
if 'orders' not in st.session_state:
    st.session_state.orders = []

def get_current_time():
    """現在時刻を取得（秒以下切り捨て）"""
    return datetime.datetime.now().replace(second=0, microsecond=0)

def add_order(type, count, location, note, target_time_dt, is_reservation):
    """注文を追加する（目標時刻付き）"""
    st.session_state.orders.append({
        "id": str(uuid.uuid4())[:8],
        "created_at": get_current_time(),
        "target_time": target_time_dt, # 顧客の希望時刻（今すぐ or 予約時間）
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
# 3. 高度シミュレーションロジック
# ==========================================

def simulate_schedule(new_orders_list, oven_count, bake_time, prep_time, driver_count, weather):
    """
    全オーダー（既存+新規）を時系列順に並べてシミュレーションする
    Return: 新規オーダーの完了予定時刻リスト
    """
    # 1. 現在のアクティブオーダーと、シミュレーション用新規オーダーを統合
    #    構造: {start_constraint, count, type, location, id}
    #    start_constraint: 調理開始可能時刻（予約なら 指定時刻 - (移動+焼成+準備)）
    
    tasks = []
    
    # A. 既存オーダーのタスク化
    for o in st.session_state.orders:
        # 調理開始したい時刻 = 希望時刻 - (調理準備 + 焼成 + 移動(デリバリーのみ))
        # ただし、すでに時間は過ぎているかもしれないので max(現在, 希望逆算) になるが
        # ここではシンプルに「オーブン投入待ち行列」を作るために「調理開始希望時刻」を算出
        
        # 簡易化のため「オーブン投入可能時刻」でソートする
        # 予約の場合：予約時刻 - (移動 + 焼成) = 焼き上がりリミット -> ここから逆算
        # 今すぐの場合：現在時刻
        
        ready_to_bake_time = o['created_at'] # デフォルトは受注時
        if o['is_reservation']:
            # 予約の場合、準備開始時間を逆算（余裕を持って、希望の30分前には焼き始めたい等）
            # ここでは「希望時刻に間に合うギリギリ」ではなく「希望時刻に向けて作業開始する時間」とする
            # 例: 18:00受取なら、17:30くらいから列に並ぶイメージ
            ready_to_bake_time = o['target_time'] - timedelta(minutes=30)
        
        # 過去の時刻は「現在」に補正
        ready_to_bake_time = max(ready_to_bake_time, get_current_time())
        
        tasks.append({
            "id": o['id'],
            "ready_time": ready_to_bake_time,
            "count": o['count'],
            "type": o['type'],
            "location": o['location'],
            "is_new": False
        })

    # B. シミュレーションしたい新規オーダーのタスク化
    for new_o in new_orders_list:
        ready_time = max(new_o['target_time'] - timedelta(minutes=30), get_current_time()) if new_o['is_reservation'] else get_current_time()
        tasks.append({
            "id": "SIMULATION",
            "ready_time": ready_time,
            "count": new_o['count'],
            "type": new_o['type'],
            "location": new_o['location'],
            "target_time": new_o['target_time'],
            "is_new": True
        })

    # C. 時系列順（焼き始めたい順）にソート
    tasks.sort(key=lambda x: x['ready_time'])

    # --- オーブンシミュレーション ---
    # オーブンごとの「空き予定時刻」
    ovens = [get_current_time()] * oven_count
    oven_interval = timedelta(minutes=1) # 投入間隔
    bake_duration = timedelta(minutes=bake_time)
    prep_duration = timedelta(minutes=prep_time)

    # 結果格納用
    simulation_results = {}

    for task in tasks:
        # ピザの枚数分、オーブン枠を確保する
        task_finish_time = get_current_time() # 初期値
        
        for _ in range(task['count']):
            # 最も早く空くオーブンを探す
            earliest_idx = ovens.index(min(ovens))
            oven_ready = ovens[earliest_idx]
            
            # 投入時刻 = max(オーブン空き, 準備完了(タスク開始時間+準備))
            # ※タスクのready_timeは「調理開始できる時間」
            entry_time = max(oven_ready, task['ready_time'] + prep_duration)
            
            # オーブン更新
            ovens[earliest_idx] = entry_time + oven_interval
            
            # 焼き上がり時刻
            finish_time = entry_time + bake_duration
            task_finish_time = max(task_finish_time, finish_time) # 最後の1枚が焼ける時間
            
        simulation_results[task['id']] = task_finish_time

    # --- デリバリー配送計算（新規のみ簡易計算） ---
    # ※既存のデリバリー待ち行列シミュレーションは複雑になるため、
    # 今回は「新規オーダーが焼き上がった時点で、配送リソースがどうなっているか」を簡易予測
    
    final_result = None
    
    # シミュレーション対象（新規）の結果を取り出す
    baked_time = simulation_results.get("SIMULATION")
    
    if not baked_time:
        return None, None # エラーガード

    # 新規注文情報の再取得
    target_new = new_orders_list[0] # 今回は1件ずつの予測前提
    
    delivery_details = {}
    total_finish_time = baked_time

    if target_new['type'] == "Delivery":
        w_conf = WEATHER_CONFIG[weather]
        zone_id = LOCATION_MAP[target_new['location']]
        dist_km = ZONE_CONFIG[zone_id]['dist_km']
        
        # 移動時間
        speed = 40.0 * w_conf["speed"]
        travel_minutes = (dist_km / speed) * 60
        travel_delta = timedelta(minutes=travel_minutes)
        
        # 配車待ち（簡易ロジック：現在アクティブなデリバリー数から推測）
        # 本来はドライバーの帰還時刻をシミュレーションすべきだが、
        # ここでは「アクティブなデリバリー件数 * 5分」をバッファとして加算する簡易モデル採用
        active_deliveries = len([t for t in tasks if t['type'] == 'Delivery' and not t['is_new']])
        wait_minutes = active_deliveries * 5 # 簡易係数
        wait_delta = timedelta(minutes=wait_minutes)
        
        total_finish_time = baked_time + wait_delta + travel_delta
        
        delivery_details = {
            "baked": baked_time.strftime("%H:%M"),
            "wait": int(wait_minutes),
            "travel": int(travel_minutes)
        }
        
    return total_finish_time, delivery_details


# ==========================================
# 4. UI構築
# ==========================================

st.set_page_config(page_title="Pizza Manager Pro", layout="wide")
st.title("🍕 店舗運営・予約管理ダッシュボード")

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
    st.subheader("📞 注文入力 & 予測")
    
    # 入力フォーム
    with st.container(border=True):
        # 予約トグル
        order_mode = st.radio("受付タイプ", ["今すぐ注文", "予約注文"], horizontal=True)
        
        current_dt = get_current_time()
        target_dt = current_dt
        
        if order_mode == "予約注文":
            # 時間入力（15分刻みなどで丸めると使いやすいが、今回は分単位）
            col_t1, col_t2 = st.columns(2)
            res_date = col_t1.date_input("日付", datetime.date.today())
            res_time = col_t2.time_input("希望時刻", (current_dt + timedelta(minutes=60)).time())
            target_dt = datetime.datetime.combine(res_date, res_time)
        
        # 基本情報
        order_type = st.selectbox("受取方法", ["Takeout", "Delivery"])
        
        c1, c2 = st.columns(2)
        count = c1.number_input("枚数", 1, 20, 1)
        loc = "鹿塩"
        if order_type == "Delivery":
            loc = c2.selectbox("お届け先", list(LOCATION_MAP.keys()))
        else:
            note = c2.text_input("顧客名/メモ", "様")
            
        # --- リアルタイム予測実行 ---
        # シミュレーション用の仮オブジェクト作成
        sim_order = {
            "type": order_type,
            "count": count,
            "location": loc,
            "target_time": target_dt,
            "is_reservation": (order_mode == "予約注文")
        }
        
        finish_dt, details = simulate_schedule(
            [sim_order], oven_count, bake_time, prep_time, driver_count, weather
        )
        
        # 結果表示
        st.divider()
        st.markdown("##### 🕒 予測完了時刻")
        
        time_diff = (finish_dt - target_dt).total_seconds() / 60
        
        # 判定ロジック
        if order_mode == "今すぐ注文":
            st.metric("提供予定", f"{finish_dt.strftime('%H:%M')}", f"あと {int((finish_dt - current_dt).total_seconds()/60)}分")
        else:
            # 予約の場合、希望時刻に間に合うか？
            if finish_dt <= target_dt:
                st.success(f"✅ 予約時刻 {target_dt.strftime('%H:%M')} に間に合います。（完了予測 {finish_dt.strftime('%H:%M')}）")
            else:
                st.error(f"⚠️ 遅延警告: {target_dt.strftime('%H:%M')} には間に合いません！")
                st.metric("最短提供可能", f"{finish_dt.strftime('%H:%M')}", f"{int(time_diff)}分遅れ")

        if details:
            st.caption(f"内訳: 焼き上がり{details['baked']} + 配車待ち{details['wait']}分 + 移動{details['travel']}分")

        # 確定ボタン
        if st.button("注文確定", type="primary", use_container_width=True):
            add_order(order_type, count, loc, 
                      note if order_type=="Takeout" else f"配送: {loc}", 
                      target_dt, (order_mode == "予約注文"))
            st.success("リストに追加しました")
            st.rerun()

    # --- 時間帯別 混雑ヒートマップ ---
    st.subheader("📅 時間帯別 混雑予測")
    st.caption("今から1枚注文した場合の提供所要時間")
    
    # 向こう3時間の1時間ごとの予測
    future_slots = []
    base_time = get_current_time().replace(minute=0) + timedelta(hours=1)
    
    for i in range(4):
        check_time = base_time + timedelta(hours=i)
        
        # 仮注文（テイクアウト1枚）でテスト
        test_order = {
            "type": "Takeout", "count": 1, "location": "", 
            "target_time": check_time, "is_reservation": True
        }
        f_dt, _ = simulate_schedule([test_order], oven_count, bake_time, prep_time, driver_count, weather)
        
        delay = (f_dt - check_time).total_seconds() / 60
        status = "🟢" if delay <= 0 else "🔴" if delay > 15 else "🟡"
        
        future_slots.append({
            "時刻": check_time.strftime("%H:00"),
            "状況": status,
            "完了予測": f_dt.strftime("%H:%M"),
            "遅れ": f"{int(delay)}分" if delay > 0 else "OK"
        })
    
    st.dataframe(pd.DataFrame(future_slots), hide_index=True, use_container_width=True)


with col_list:
    st.subheader("📋 オーダーリスト")
    
    if st.session_state.orders:
        # 時系列順にソートして表示
        sorted_orders = sorted(st.session_state.orders, key=lambda x: x['target_time'])
        
        for o in sorted_orders:
            # 表示色の切り替え
            is_late = False # 簡易判定（本来は再計算が必要だがUI上は省略）
            
            icon = "📅" if o['is_reservation'] else "⚡"
            bg_color = "red" if is_late else "gray"
            
            label = f"{icon} {o['target_time'].strftime('%H:%M')} | {o['note']} ({o['count']}枚)"
            
            with st.expander(label):
                c1, c2 = st.columns([3, 1])
                c1.write(f"タイプ: {o['type']}")
                c1.write(f"場所: {o['location']}")
                
                if c2.button("完了", key=o['id']):
                    complete_order(o['id'])
                    st.rerun()
    else:
        st.info("オーダーはありません")

# データ確認用
with st.expander("Debug"):
    st.write(st.session_state.orders)