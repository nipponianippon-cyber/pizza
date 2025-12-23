import math
import streamlit as st

# ==========================================
# 設定・マスタデータ (共通 & デリバリー用)
# ==========================================

# 距離区分とマッピング
ZONE_CONFIG = {
    "Zone_A": {"label": "近距離エリア", "dist_km": 1.0},
    "Zone_B": {"label": "中距離エリア", "dist_km": 2.0},
    "Zone_C": {"label": "遠距離エリア", "dist_km": 4.0},
    "Zone_D": {"label": "特遠エリア",   "dist_km": 6.0},
}

LOCATION_MAP = {
    "鹿塩": "Zone_A",
    "大吹": "Zone_A",
    "亀井": "Zone_A",
    "末成": "Zone_A",
    "大成": "Zone_A",
    "小林": "Zone_A",
    "光明": "Zone_A",
    "高司": "Zone_A",
    "段上(1~4)": "Zone_B",
    "千種": "Zone_B",
    "仁川": "Zone_B",
    "仁川高台": "Zone_B",
    "仁川高丸": "Zone_B",
    "仁川(5~6)": "Zone_C",
    "上ヶ原": "Zone_C",
    "上甲東園": "Zone_B",
    "甲東園": "Zone_B",
    "上大市": "Zone_C",
    "下大市": "Zone_C",
    "段上(5~8)": "Zone_C",
    "安倉西": "Zone_B",
    "安倉中": "Zone_B",
    "西野": "Zone_B",
    "中野西": "Zone_B",
    "中野北": "Zone_B",
    "美座": "Zone_C",
    "小浜": "Zone_C",
    "弥生": "Zone_C",
    "福井": "Zone_A",
    "末広": "Zone_B",
    "中州": "Zone_B",
    "逆瀬川": "Zone_A",
    "南口": "Zone_C",
    "光が丘": "Zone_C",
    "青葉台": "Zone_C",
    "寿楽荘": "Zone_C",
    "長寿が丘": "Zone_D",
    "月見山": "Zone_D",
    "宝松苑": "Zone_C",
    "逆瀬台": "Zone_C",
    "野上(1~3)": "Zone_B",
    "野上(4~6)": "Zone_C"
}

# 天候設定
WEATHER_CONFIG = {
    "晴": {"speed": 1.0, "stack": 1.0},
    "雨": {"speed": 0.8, "stack": 0.8}
}

# ==========================================
# 計算ロジック関数
# ==========================================

def calc_takeout_time(new_order, backlog, oven_count, bake_time, prep_time):
    """
    テイクアウト用：オーブンの空き状況シミュレーション
    """
    # オーブンの初期状態（すべて空き=0.0）
    ovens = [0.0] * oven_count
    oven_interval = 1.0 # 1枚投入にかかる間隔(分)

    # 1. バックログ（予約分）を先に割り当てて埋める
    for _ in range(backlog):
        earliest_idx = ovens.index(min(ovens))
        ovens[earliest_idx] += oven_interval

    # 2. 新規注文を割り当て
    last_finish_time = 0.0
    
    for _ in range(new_order):
        earliest_idx = ovens.index(min(ovens))
        
        # 投入可能 = max(オーブンの空き, 調理準備完了)
        entry_time = max(ovens[earliest_idx], prep_time)
        
        # 次の予約のためにオーブン時間を更新
        ovens[earliest_idx] = entry_time + oven_interval
        
        # 焼き上がり時刻
        finish_time = entry_time + bake_time
        last_finish_time = finish_time
        
    return int(last_finish_time)


def calc_delivery_time(location, order_queue, driver_count, weather, prep_time):
    """
    デリバリー用：ドライバーの回転率シミュレーション
    """
    # マスタ取得
    zone_id = LOCATION_MAP[location]
    zone_info = ZONE_CONFIG[zone_id]
    dist_km = zone_info["dist_km"]
    w_conf = WEATHER_CONFIG[weather]

    # 能力計算
    per_driver_capa = math.floor(3 * w_conf["stack"]) # 基本3枚持ち
    if per_driver_capa < 1: per_driver_capa = 1
    
    fleet_capa = driver_count * per_driver_capa # 全体の1回あたりの運搬能力
    
    # 何回転目か？ (待ち + 自分1件)
    rounds = math.ceil((order_queue + 1) / fleet_capa)
    
    # 時間計算
    # 1回転30分と仮定 / 天候による速度係数
    round_trip_time = 30 / w_conf["speed"]
    wait_time = max(0, (rounds - 1) * round_trip_time)
    
    # 移動時間 (時速40kmベース)
    travel_speed = 40.0 * w_conf["speed"]
    travel_time = (dist_km / travel_speed) * 60
    
    total_time = int(prep_time + wait_time + travel_time)
    
    return {
        "total": total_time,
        "prep": prep_time,
        "wait": int(wait_time),
        "travel": int(travel_time),
        "dist": dist_km,
        "zone": zone_info["label"]
    }

# ==========================================
# UI構築
# ==========================================

st.set_page_config(page_title="granma")

st.title("⏱️ 店舗・配送 総合待ち時間予測")
st.markdown("状況に合わせてタブを切り替えてください。")

# タブの作成
tab1, tab2 = st.tabs(["take out", "deliverly"])

# --- 共通サイドバー設定 ---
with st.sidebar:
    st.header("setting")
    prep_time = st.number_input("基本調理時間 (分)", 10, 60, 15)
    
    st.divider()
    st.markdown("**デリバリー環境**")
    weather = st.radio("weather", ["晴", "雨", "雪"], horizontal=True)
    driver_count = st.slider("稼働ドライバー数", 1, 10, 3)
    
    st.divider()
    st.markdown("**キッチン環境**")
    oven_count = st.slider("ovens", 1, 5, 2)
    bake_time = st.number_input("焼成時間 (分)", 3.0, 15.0, 6.5)


# === タブ1: テイクアウト計算 ===
with tab1:
    st.subheader("お持ち帰り時間予測")
    st.info("オーブンの空き状況と予約残数から計算します。")
    
    col1, col2 = st.columns(2)
    with col1:
        to_order_count = st.number_input("あなたの注文枚数", 1, 20, 1, key="to_new")
    with col2:
        to_backlog = st.number_input("現在の予約待ち枚数", 0, 100, 5, key="to_back")

    if st.button("受取時間を計算", key="btn_takeout", type="primary"):
        result_min = calc_takeout_time(
            to_order_count, to_backlog, oven_count, bake_time, prep_time
        )
        
        st.divider()
        st.metric(label="商品受け渡しまで", value=f"{result_min} 分")
        
        # 状況に応じたメッセージ
        if result_min <= prep_time + bake_time + 2:
            st.success("待ち時間なし！スムーズにお渡しできます。")
        else:
            st.warning(f"予約が混み合っており、通常より{int(result_min - (prep_time+bake_time))}分ほどお待ちいただきます。")


# === タブ2: デリバリー計算 ===
with tab2:
    st.subheader("宅配・到着時間予測")
    st.info("ドライバーの稼働率と天候、距離から計算します。")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        del_loc = st.selectbox("お届け先", list(LOCATION_MAP.keys()))
    with col2:
        del_queue = st.number_input("現在の配達待ち件数", 0, 50, 5)

    if st.button("到着時間を計算", key="btn_delivery", type="primary"):
        res = calc_delivery_time(
            del_loc, del_queue, driver_count, weather, prep_time
        )
        
        st.divider()
        st.metric(label="到着予定時間", value=f"{res['total']} 分")
        
        st.write("▼ 時間の内訳")
        c1, c2, c3 = st.columns(3)
        c1.metric("調理", f"{res['prep']}分")
        c2.metric("配車待ち", f"{res['wait']}分")
        c3.metric("移動", f"{res['travel']}分", help=f"距離: {res['dist']}km")
        
        st.caption(f"エリア: {res['zone']} / 天候: {weather}")

# --- デバッグ用 ---
with st.expander("管理者用データ確認"):
    st.json(ZONE_CONFIG)