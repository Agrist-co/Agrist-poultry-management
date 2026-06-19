import os
import json
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from PIL import Image, ImageDraw, ImageFont
import locale

# ==============================================================================
# 🌐 サーバーの地域設定（ロケール）を強制的に日本語に設定
# ==============================================================================
try:
    locale.setlocale(locale.LC_ALL, 'ja_JP.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Japanese_Japan.932')
    except locale.Error:
        pass

# ページのレイアウト設定
st.set_page_config(layout="wide", page_title="鶏舎飼料管理システム")

# --- 📁 ディレクトリ管理 ---
BASE_DIR = os.path.abspath('./鶏舎飼料管理データ') + '/'
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)
LATEST_SESSION_FILE = os.path.join(BASE_DIR, "latest_session.json")

# ==============================================================================
# 🎯 日本語フォント確保関数
# ==============================================================================
FONT_PATH = "/tmp/ipaexg.ttf"
def ensure_japanese_font():
    if not os.path.exists(FONT_PATH):
        try:
            import urllib.request
            url = "https://github.com/orandataro/ipaexg-font/raw/master/ipaexg.ttf"
            urllib.request.urlretrieve(url, FONT_PATH)
        except:
            pass
    return FONT_PATH if os.path.exists(FONT_PATH) else None

ensure_japanese_font()

# ==============================================================================
# Ross 308 標準指標データ
# ==============================================================================
ROSS308_STD = [
    (0, 44, 0.0, 0), (1, 62, 0.196, 12), (2, 81, 0.352, 16), (3, 102, 0.476, 20),
    (4, 125, 0.577, 24), (5, 151, 0.658, 27), (6, 181, 0.724, 31), (7, 213, 0.780, 35),
    (8, 249, 0.826, 39), (9, 288, 0.865, 44), (10, 330, 0.900, 48), (11, 376, 0.930, 52),
    (12, 425, 0.957, 57), (13, 477, 0.982, 62), (14, 533, 1.005, 67), (15, 592, 1.026, 72),
    (16, 655, 1.047, 77), (17, 720, 1.066, 83), (18, 789, 1.086, 88), (19, 860, 1.105, 94),
    (20, 935, 1.123, 100), (21, 1012, 1.142, 105), (22, 1092, 1.160, 111), (23, 1174, 1.178, 117),
    (24, 1258, 1.196, 122), (25, 1345, 1.214, 128), (26, 1434, 1.233, 134), (27, 1524, 1.251, 139),
    (28, 1616, 1.269, 145), (29, 1710, 1.288, 150), (30, 1805, 1.306, 156), (31, 1901, 1.325, 161),
    (32, 1999, 1.343, 166), (33, 2097, 1.362, 171), (34, 2196, 1.381, 176), (35, 2296, 1.399, 180),
    (36, 2396, 1.418, 185), (37, 2496, 1.437, 189), (38, 2597, 1.456, 193), (39, 2697, 1.474, 197),
    (40, 2798, 1.493, 201), (41, 2898, 1.512, 204), (42, 2998, 1.531, 207), (43, 3097, 1.550, 211),
    (44, 3197, 1.569, 213), (45, 3295, 1.587, 216), (46, 3393, 1.606, 219), (47, 3490, 1.625, 221),
    (48, 3586, 1.644, 223), (49, 3681, 1.663, 225), (50, 3776, 1.681, 227), (51, 3869, 1.700, 229),
    (52, 3961, 1.719, 230), (53, 4052, 1.738, 231), (54, 4142, 1.756, 233), (55, 4230, 1.775, 233),
    (56, 4318, 1.793, 234)
]

# ==============================================================================
# 🔄 入力欄の初期値をセッション状態（記憶）へセット
# ==============================================================================
def init_field(key, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value

init_field("v_farm_name", "上川西農場")
init_field("v_start_date", date(2026, 6, 9))
init_field("v_birds", 6600)
init_field("v_shipping_age", 46)
init_field("v_house_no", "A棟")
init_field("v_tank_cap", 7000)
init_field("v_min_alert", 500)
init_field("v_first_qty", 5000)
init_field("v_tank_no", "No.1")
init_field("v_std_qty", 4000)
init_field("v_pre_limit", 6000)
init_field("v_mid_limit", 10000)

if "current_records" not in st.session_state:
    st.session_state.current_records = {0: {"delivered": st.session_state.v_first_qty, "actual_tank": st.session_state.v_first_qty, "type": "確定"}}
if "current_adjustments" not in st.session_state:
    st.session_state.current_adjustments = {}

# 最初の一回だけ、前回セッションがあれば自動復元
if "initialized" not in st.session_state:
    if os.path.exists(LATEST_SESSION_FILE):
        try:
            with open(LATEST_SESSION_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            st.session_state.current_records = {int(k): v for k, v in loaded["records"].items()}
            st.session_state.current_adjustments = {int(k): v for k, v in loaded.get("adjustments", {}).items()}
            for k in loaded:
                if f"v_{k}" in st.session_state:
                    if k == "start_date":
                        st.session_state[f"v_{k}"] = datetime.strptime(loaded[k], "%Y-%m-%d").date()
                    else:
                        st.session_state[f"v_{k}"] = loaded[k]
        except:
            pass
    st.session_state.initialized = True

def scan_directory():
    data_tree = {}
    if not os.path.exists(BASE_DIR): return data_tree
    try:
        for farm in sorted(os.listdir(BASE_DIR)):
            farm_path = os.path.join(BASE_DIR, farm)
            if os.path.isdir(farm_path):
                data_tree[farm] = {}
                for house in sorted(os.listdir(farm_path)):
                    house_path = os.path.join(farm_path, house)
                    if os.path.isdir(house_path):
                        data_tree[farm][house] = {}
                        for tank in sorted(os.listdir(house_path)):
                            tank_path = os.path.join(house_path, tank)
                            if os.path.isdir(tank_path):
                                data_tree[farm][house][tank] = []
                                for f in sorted(os.listdir(tank_path)):
                                    if f.endswith('.json') and f != "latest_session.json":
                                        data_tree[farm][house][tank].append(f.replace('.json', ''))
    except:
        pass
    return data_tree

def calculate_table_core(param_dict, rec_dict, adj_dict):
    birds = param_dict["birds"]
    shipping_age = min(param_dict["shipping_age"], 56)
    tank_cap = param_dict["tank_cap"]
    min_alert = param_dict["min_alert"]
    std_qty = param_dict["std_qty"]
    pre_limit = param_dict["pre_limit"]
    mid_limit = param_dict["mid_limit"]
    first_qty = param_dict["first_qty"]
    
    start_date_val = param_dict["start_date"]
    if isinstance(start_date_val, str):
        start_date_val = datetime.strptime(start_date_val, "%Y-%m-%d").date()

    df = pd.DataFrame(ROSS308_STD, columns=["day", "weight", "fcr", "std_intake_g"])
    df = df[df["day"] <= shipping_age].reset_index(drop=True)

    df["date_obj"] = [start_date_val + timedelta(days=int(d)) for d in df["day"]]
    df["date"] = [d.strftime("%m/%d") for d in df["date_obj"]]
    df["std_feed_kg"] = (df["std_intake_g"] * birds) / 1000.0
    if 45 in df["day"].values: df.loc[df["day"] == 45, "std_feed_kg"] *= 0.75

    act_dict = {d: v for d, v in rec_dict.items() if v.get("type") == "確定"}
    adj_rates = np.ones(len(df))
    actual_feed = df["std_feed_kg"].copy().values
    sorted_act_days = sorted(act_dict.keys())
    latest_rate = 1.0

    if len(sorted_act_days) > 1:
        for i in range(len(sorted_act_days) - 1):
            start_day = sorted_act_days[i]
            end_day = sorted_act_days[i + 1]
            prev_start_total = act_dict[start_day]["actual_tank"] + (act_dict[start_day]["delivered"] if start_day > 0 else 0)
            if start_day == 0: prev_start_total = first_qty
                
            current_morning_tank = act_dict[end_day]["actual_tank"]
            actual_consumed = prev_start_total - current_morning_tank
            std_consumed = df.loc[start_day:end_day-1, "std_feed_kg"].sum()
            rate_period = actual_consumed / std_consumed if std_consumed > 0 else 1.0
            latest_rate = rate_period
            
            for d in range(start_day, end_day):
                adj_rates[d] = rate_period
                actual_feed[d] = df.loc[d, "std_feed_kg"] * rate_period

    last_act_day = sorted_act_days[-1] if sorted_act_days else 0
    for d in range(0, len(df)):
        if d >= last_act_day and last_act_day > 0:
            actual_feed[d] = df.loc[d, "std_feed_kg"] * latest_rate
            adj_rates[d] = latest_rate

    df["adj_rate"] = adj_rates
    df["act_feed_kg"] = actual_feed
    df["act_intake_g"] = (df["act_feed_kg"] * 1000.0) / birds

    pred_tank_morning = np.zeros(len(df))
    real_tank_morning = np.zeros(len(df))
    delivery_plan = np.zeros(len(df))
    event_notes = [""] * len(df)

    pred_tank_morning[0] = first_qty
    real_tank_morning[0] = first_qty
    event_notes[0] = f"【初回】前期: {first_qty:.0f}kg"
    allocated_pre = first_qty
    allocated_mid = 0.0
    evening_pred_tank = first_qty - df.loc[0, "act_feed_kg"]

    for d in range(1, len(df)):
        if d <= last_act_day and last_act_day > 0:
            if d in act_dict:
                delivery_plan[d] = act_dict[d]["delivered"]
                real_tank_morning[d] = act_dict[d]["actual_tank"]
                event_notes[d] = f"【実績確定】納品前残量: {act_dict[d]['actual_tank']:.0f}kg"
                if pre_limit > 0 and allocated_pre < pre_limit: allocated_pre += delivery_plan[d]
                elif mid_limit > 0 and allocated_mid < mid_limit: allocated_mid += delivery_plan[d]
            else: real_tank_morning[d] = evening_pred_tank
            pred_tank_morning[d] = real_tank_morning[d]
            evening_pred_tank = real_tank_morning[d] + delivery_plan[d] - df.loc[d, "act_feed_kg"]
        else:
            real_tank_morning[d] = np.nan
            pred_tank_morning[d] = evening_pred_tank
            if d in adj_dict:
                adj_info = adj_dict[d]
                delivery_plan[d] = adj_info["delivered"]
                event_notes[d] = f"【調整配車】納品量: {adj_info['delivered']:.0f}kg"
                if adj_info["actual_tank"] is not None:
                    pred_tank_morning[d] = adj_info["actual_tank"]
                    real_tank_morning[d] = adj_info["actual_tank"]
            else:
                tomorrow_need = df.loc[d, "act_feed_kg"]
                if pred_tank_morning[d] <= min_alert or pred_tank_morning[d] < tomorrow_need:
                    delivery_plan[d] = std_qty
                    
                    rem_pre = pre_limit - allocated_pre if pre_limit > 0 else 0
                    if rem_pre > 0:
                        if rem_pre >= std_qty:
                            allocated_pre += std_qty
                            event_notes[d] = f"【通常発注】前期: {std_qty}kg"
                        else:
                            mix_next = std_qty - rem_pre
                            allocated_pre += rem_pre
                            if mid_limit > 0:
                                allocated_mid += mix_next
                                event_notes[d] = f"【混載発注】前期: {rem_pre:.0f}kg / 中期: {mix_next:.0f}kg"
                            else:
                                event_notes[d] = f"【混載発注】前期: {rem_pre:.0f}kg / 仕上: {mix_next:.0f}kg"
                    else:
                        rem_mid = mid_limit - allocated_mid if mid_limit > 0 else 0
                        if rem_mid > 0:
                            if rem_mid >= std_qty:
                                allocated_mid += std_qty
                                event_notes[d] = f"【通常発注】中期: {std_qty}kg"
                            else:
                                mix_fin = std_qty - rem_mid
                                allocated_mid += rem_mid
                                event_notes[d] = f"【混載発注】中期: {rem_mid:.0f}kg / 仕上: {mix_fin:.0f}kg"
                        else:
                            event_notes[d] = f"【通常発注】仕上: {std_qty}kg"
            evening_pred_tank = pred_tank_morning[d] + delivery_plan[d] - df.loc[d, "act_feed_kg"]

    df["pred_tank_morning"] = pred_tank_morning
    df["real_tank_morning"] = real_tank_morning
    df["delivery_kg"] = delivery_plan
    df["event_notes"] = event_notes
    return df

def get_east_asian_width(text):
    import unicodedata
    count = 0
    for c in text:
        if unicodedata.east_asian_width(c) in 'FWA': count += 2
        else: count += 1
    return count

def pad_to_width(text, target_width, align='left'):
    text = str(text)
    current_w = get_east_asian_width(text)
    if current_w >= target_width: return text
    padding = ' ' * (target_width - current_w)
    if align == 'center':
        left_pad = ' ' * ((target_width - current_w) // 2)
        right_pad = ' ' * (target_width - current_w - len(left_pad))
        return left_pad + text + right_pad
    elif align == 'right': return padding + text
    else: return text + padding


# ==============================================================================
# 🧱 UI構築（入力部品に完全に Session State キーを紐付け）
# ==============================================================================
main_tabs = st.tabs(["📋 1. 飼料計算シミュレーター", "📸 2. 飼料発注"])

with main_tabs[0]:
    st.subheader("📂 ステップ1：初期条件・環境設定")
    col1, col2, col3 = st.columns(3)
    with col1:
        farm_name = st.text_input("農場名:", key="v_farm_name")
        start_date = st.date_input("入雛日:", format="YYYY/MM/DD", key="v_start_date")
        birds = st.number_input("入雛羽数(羽):", step=100, key="v_birds")
        shipping_age = st.number_input("出荷日齢:", max_value=56, key="v_shipping_age")
    with col2:
        house_no = st.text_input("鶏舎No./名:", key="v_house_no")
        tank_cap = st.number_input("タンク容量(kg):", step=500, key="v_tank_cap")
        min_alert = st.number_input("最低残量アラート(kg):", step=100, key="v_min_alert")
        first_qty = st.number_input("初回納品量(kg):", step=500, key="v_first_qty")
    with col3:
        tank_no = st.text_input("タンクNo.:", key="v_tank_no")
        std_qty = st.number_input("通常配送単位(kg):", step=500, key="v_std_qty")
        pre_limit = st.number_input("前期飼料総量(kg):", step=500, key="v_pre_limit")
        mid_limit = st.number_input("中期飼料総量(kg):", step=500, key="v_mid_limit")

    if st.button("① 新規条件で台帳作成（全クリア）", type="primary"):
        st.session_state.current_records = {0: {"delivered": first_qty, "actual_tank": first_qty, "type": "確定"}}
        st.session_state.current_adjustments = {}
        st.success("🆕 初期条件でクリアした台帳を作成しました。")

    st.markdown("---")
    st.subheader("🔍 ステップ2：過去データの絞り込み読込・保存")
    tree = scan_directory()
    farms_list = list(tree.keys()) if tree else []
    if not farms_list: farms_list = ["(保存データなし)"]
        
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1: sel_farm = st.selectbox("農場選択:", farms_list)
    with col_s2:
        houses = list(tree[sel_farm].keys()) if (sel_farm in tree and tree[sel_farm]) else ["—"]
        sel_house = st.selectbox("鶏舎選択:", houses)
    with col_s3:
        tanks = list(tree[sel_farm][sel_house].keys()) if (sel_farm in tree and sel_house in tree[sel_farm] and tree[sel_farm][sel_house]) else ["—"]
        sel_tank = st.selectbox("タンク選択:", tanks)
    with col_s4:
        dates = tree[sel_farm][sel_house][sel_tank] if (sel_farm in tree and sel_house in tree[sel_farm] and sel_tank in tree[sel_farm][sel_house]) else ["—"]
        sel_date = st.selectbox("入雛日選択:", dates)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📂 選択したデータを読込", type="primary", key="load_btn"):
            if sel_farm != "(保存データなし)" and sel_date != "—":
                try:
                    filepath = os.path.join(BASE_DIR, sel_farm, sel_house, sel_tank, f"{sel_date}.json")
                    with open(filepath, 'r', encoding='utf-8') as f: 
                        loaded = json.load(f)
                    
                    # 🎯 【超重要修正】読み込んだ過去データをSession State側へ強制反映
                    st.session_state.v_farm_name = loaded["farm_name"]
                    st.session_state.v_house_no = loaded["house_no"]
                    st.session_state.v_tank_no = loaded["tank_no"]
                    st.session_state.v_start_date = datetime.strptime(loaded["start_date"], "%Y-%m-%d").date()
                    st.session_state.v_birds = loaded["birds"]
                    st.session_state.v_shipping_age = loaded["shipping_age"]
                    st.session_state.v_tank_cap = loaded["tank_cap"]
                    st.session_state.v_min_alert = loaded["min_alert"]
                    st.session_state.v_first_qty = loaded["first_qty"]
                    st.session_state.v_std_qty = loaded["std_qty"]
                    st.session_state.v_pre_limit = loaded.get("pre_limit", 6000)
                    st.session_state.v_mid_limit = loaded.get("mid_limit", 10000)
                    
                    st.session_state.current_records = {int(k): v for k, v in loaded["records"].items()}
                    st.session_state.current_adjustments = {int(k): v for k, v in loaded.get("adjustments", {}).items()}
                    
                    st.success(f"📂 【{sel_farm} / {sel_house} ({sel_date})】の過去データを完全展開しました！")
                    st.rerun() # 画面全体の表示を一発で過去データに切り替えるためのリフレッシュ
                except Exception as e: st.error(f"⚠️ 読込失敗: {e}")
            else: st.warning("⚠️ 読み込むデータが選択されていません。")
                
    with col_btn2:
        if st.button("💾 全体の状態をファイルへ保存", type="primary", key="save_btn"):
            try:
                target_dir = os.path.join(BASE_DIR, farm_name, house_no, tank_no)
                os.makedirs(target_dir, exist_ok=True)
                filepath = os.path.join(target_dir, f"{start_date.strftime('%Y-%m-%d')}.json")
                save_data = {
                    "farm_name": farm_name, "house_no": house_no, "tank_no": tank_no, "start_date": start_date.strftime('%Y-%m-%d'),
                    "birds": birds, "shipping_age": shipping_age, "tank_cap": tank_cap, "min_alert": min_alert, "first_qty": first_qty,
                    "std_qty": std_qty, "pre_limit": pre_limit, "mid_limit": mid_limit, "records": st.session_state.current_records, "adjustments": st.session_state.current_adjustments
                }
                with open(filepath, 'w', encoding='utf-8') as f: json.dump(save_data, f, ensure_ascii=False, indent=4)
                with open(LATEST_SESSION_FILE, 'w', encoding='utf-8') as f: json.dump(save_data, f, ensure_ascii=False, indent=4)
                st.success(f"💾 「{farm_name}」のデータを正常に保存しました！")
                st.rerun()
            except Exception as e: st.error(f"⚠️ 保存失敗: {e}")

    # 現在画面に表示されている(あるいは読み込まれた)値を元に台帳を計算
    params = {"birds": birds, "shipping_age": shipping_age, "tank_cap": tank_cap, "min_alert": min_alert, "std_qty": std_qty, "pre_limit": pre_limit, "mid_limit": mid_limit, "start_date": start_date, "first_qty": first_qty}
    df_result = calculate_table_core(params, st.session_state.current_records, st.session_state.current_adjustments)

    st.markdown("---")
    st.subheader("📊 ステップ3：日付ベース実績・計画入力")
    date_options = [df_result.loc[idx, "date"] for idx in range(len(df_result))]
    act_date = st.selectbox("対象の日付を選択:", date_options)
    target_day_idx = date_options.index(act_date)
    stock_val = df_result.loc[target_day_idx, "pred_tank_morning"]
    st.info(f"💡 選択した {act_date} の補正後予定残量（朝）: **{stock_val:,.1f} kg**")

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        st.markdown("<b style='color:#f57c00;'>【A】手動調整・調整配車（未来予測の変更）</b>", unsafe_allow_html=True)
        adj_qty = st.number_input("調整納品数量(kg):", value=4000, step=500)
        adj_tank = st.number_input("調整時実質残量(kg):", value=int(stock_val), step=500)
        if st.button("⚙️ 調整配車として反映"):
            st.session_state.current_adjustments[target_day_idx] = {"delivered": adj_qty, "actual_tank": adj_tank, "type": "調整配車"}
            st.success(f"⚙️ {act_date} に手動調整を反映しました。")
            st.rerun()
    with col_input2:
        st.markdown("<b style='color:#388e3c;'>【B】実績の完全確定入力（過去データの固定化）</b>", unsafe_allow_html=True)
        act_delivered = st.number_input("実際の納品量(kg):", value=4000, step=500)
        act_tank = st.number_input("納品時のタンク残量(kg):", value=1000, step=500)
        if st.button("🏁 実績として確定保存して再計算"):
            st.session_state.current_records[target_day_idx] = {"delivered": act_delivered, "actual_tank": act_tank, "type": "確定"}
            if target_day_idx in st.session_state.current_adjustments: del st.session_state.current_adjustments[target_day_idx]
            st.success(f"🏁 {act_date} の実績データを固定しました。")
            st.rerun()

    st.markdown("---")
    st.subheader(f"📑 飼料総合管理台帳  [{farm_name} / {house_no} / {tank_no}]")
    disp_df = pd.DataFrame()
    disp_df["日齢"] = df_result["day"].astype(str) + "日齢"
    disp_df["日付"] = df_result["date"]
    disp_df["標準体重"] = df_result["weight"].map('{:,.0f}g'.format)
    disp_df["補正採食(1羽)"] = df_result["act_intake_g"].map('{:.1f}g'.format)
    disp_df["期間補正率"] = df_result["adj_rate"].map('{:.1%}'.format)
    disp_df["1日消費(群)"] = df_result["act_feed_kg"].map('{:,.1f}kg'.format)
    disp_df["予測残量(朝)"] = df_result["pred_tank_morning"].map('{:,.1f}kg'.format)
    disp_df["実質残量(実績)"] = df_result["real_tank_morning"].apply(lambda x: f"{x:,.1f}kg" if not np.isnan(x) else "—")
    disp_df["納品計画"] = df_result["delivery_kg"].apply(lambda x: f"{x:,.0f}kg" if x > 0 else "")
    disp_df["運行・予測備考"] = df_result["event_notes"]
    st.dataframe(disp_df, use_container_width=True, height=500)

with main_tabs[1]:
    st.subheader("🚚 ２．飼料発注シミュレーション画像生成")
    current_tree = scan_directory()
    report_farms = list(current_tree.keys()) if current_tree else ["(保存データなし)"]
    
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1: report_farm = st.selectbox("発注対象農場:", report_farms, key="report_farm")
    with col_r2: report_start = st.date_input("検索開始日:", date(2026, 6, 1), format="YYYY/MM/DD")
    with col_r3: report_end = st.date_input("検索終了日:", date(2026, 7, 31), format="YYYY/MM/DD")

    if st.button("📸 飼料発注プレビュー画面を起動", type="primary", key="report_gen_btn"):
        if report_farm == "(保存データなし)": st.error("⚠️ 発注対象となる保存データが存在しません。")
        else:
            today_str = date.today().strftime('%Y年%m月%d日')
            W_DATE = 14; W_HOUSE = 12; W_TANK = 12; W_AGE = 10; W_NOTE = 44
            TOTAL_WIDTH = W_DATE + W_HOUSE + W_TANK + W_AGE + W_NOTE + 6
            lines = [
                "+" + "-" * (TOTAL_WIDTH - 2) + "+", f"|{pad_to_width('【飼料 配車発注依頼書】', TOTAL_WIDTH - 2, 'center')}|", "+" + "-" * (TOTAL_WIDTH - 2) + "+",
                f" 発信元：長門アグリスト", f" 対象農場：{report_farm}", f" レポート発注日：{today_str}", f" 対象期間：{report_start.strftime('%Y/%m/%d')} 〜 {report_end.strftime('%Y/%m/%d')}",
                "-" * TOTAL_WIDTH, " 下記の通り、指定期間内の飼料発注・配車を依頼いたします。ご確認のほどお願い致します。", "-" * TOTAL_WIDTH, ""
            ]
            SEP_LINE = "+" + "-" * W_DATE + "+" + "-" * W_HOUSE + "+" + "-" * W_TANK + "+" + "-" * W_AGE + "+" + "-" * W_NOTE + "+"
            lines.append(SEP_LINE)
            lines.append(f"|{pad_to_width('納品予定日', W_DATE, 'center')}|{pad_to_width('鶏舎名', W_HOUSE, 'center')}|{pad_to_width('タンク番号', W_TANK, 'center')}|{pad_to_width('日齢', W_AGE, 'center')}|{pad_to_width('指示備考詳細（数量・銘柄）', W_NOTE, 'center')}|")
            lines.append(SEP_LINE)
            
            farm_dir = os.path.join(BASE_DIR, report_farm)
            all_plans = []
            if os.path.exists(farm_dir):
                for house in sorted(os.listdir(farm_dir)):
                    house_path = os.path.join(farm_dir, house)
                    if not os.path.isdir(house_path): continue
                    for tank in sorted(os.listdir(house_path)):
                        tank_path = os.path.join(house_path, tank)
                        if not os.path.isdir(tank_path): continue
                        for file in sorted(os.listdir(tank_path)):
                            if file.endswith('.json') and file != "latest_session.json":
                                try:
                                    with open(os.path.join(tank_path, file), 'r', encoding='utf-8') as f: loaded = json.load(f)
                                    p = {"birds": loaded["birds"], "shipping_age": loaded["shipping_age"], "tank_cap": loaded["tank_cap"], "min_alert": loaded["min_alert"], "std_qty": loaded["std_qty"], "pre_limit": loaded["pre_limit"], "mid_limit": loaded["mid_limit"], "start_date": loaded["start_date"], "first_qty": loaded["first_qty"]}
                                    res_df = calculate_table_core(p, {int(k): v for k, v in loaded["records"].items()}, {int(k): v for k, v in loaded.get("adjustments", {}).items()})
                                    for idx, row in res_df.iterrows():
                                        d_obj = row["date_obj"]
                                        if isinstance(d_obj, str): d_obj = datetime.strptime(d_obj, "%Y-%m-%d").date()
                                        if report_start <= d_obj <= report_end and row["delivery_kg"] > 0 and row["day"] > 0:
                                            all_plans.append({"date_str": d_obj.strftime("%Y/%m/%d"), "house": house, "tank": tank, "age": f"{row['day']}日齢", "note": str(row["event_notes"]).replace("🚚", "").strip(), "sort_date": d_obj})
                                except: pass
            if all_plans:
                all_plans.sort(key=lambda x: (x["sort_date"], x["house"], x["tank"]))
                for item in all_plans:
                    lines.append(f"|{pad_to_width(item['date_str'], W_DATE, 'center')}|{pad_to_width(item['house'], W_HOUSE, 'center')}|{pad_to_width(item['tank'], W_TANK, 'center')}|{pad_to_width(item['age'], W_AGE, 'center')}|{pad_to_width(f' {item['note']}', W_NOTE, 'left')}|")
                    lines.append(SEP_LINE)
                lines.append(f"\n 以上、合計 【 {len(all_plans)} 件 】。配車手配のほど宜しくお願い致します。")
            else:
                lines.append(f"|{pad_to_width(' 指定された期間内に納品予定のあるタンクはありませんでした（エサは十分足りています）。', TOTAL_WIDTH - 2, 'left')}|")
                lines.append(SEP_LINE)

            image = Image.new("RGB", (1240, 1754), "white")
            draw = ImageDraw.Draw(image)
            valid_font_path = ensure_japanese_font()
            if valid_font_path: font = ImageFont.truetype(valid_font_path, 24)
            else: font = ImageFont.load_default()
            for i, line_txt in enumerate(lines):
                draw.text((50, 70 + (i * 34)), line_txt, fill="black", font=font)
            st.success("📸 A4高画質プレビュー画面を正常生成しました！")
            st.image(image, caption="配車発注依頼書 プレビュー", use_container_width=True)
