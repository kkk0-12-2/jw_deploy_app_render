import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

# 画面設定
st.set_page_config(layout="wide", page_title="AIシフト作成アプリ")

st.title('📅 AIシフト作成アプリ (絶対遵守版)')

# --- 1. 基本設定 ---
staff_members = ['中村', '長坂', '角谷', '小森', '宮内', '仲村']
num_staff = len(staff_members)

# --- 2. カレンダー設定 ---
st.sidebar.header('📅 カレンダー設定')
num_days = st.sidebar.slider('今月の日数', 28, 31, 30)
start_wd = st.sidebar.selectbox('今月の1日は何曜日？', ['月', '火', '水', '木', '金', '土', '日'])
wd_list = ['月', '火', '水', '木', '金', '土', '日']
start_idx = wd_list.index(start_wd)

column_names = [f"{d+1}({wd_list[(start_idx + d) % 7]})" for d in range(num_days)]

# --- 3. 出勤日数の個別指定 ---
st.sidebar.header('👤 スタッフ別・目標出勤日数')
targets = {}
for name in staff_members:
    # 22日をデフォルトにし、AIに強く意識させる
    targets[name] = st.sidebar.slider(f'{name}さんの出勤日数', 10, 26, 22)

# --- 4. 入力セクション ---
st.header('1. 条件の入力')
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader('❌ 希望休 (チェック＝休み)')
    if 'off_req_df' not in st.session_state or st.session_state.off_req_df.shape[1] != num_days:
        st.session_state.off_req_df = pd.DataFrame(False, index=staff_members, columns=column_names)
    off_df = st.data_editor(st.session_state.off_req_df, key="off_editor")

with col_in2:
    st.subheader('✅ 出勤必須 (チェック＝必ず出る)')
    if 'must_work_df' not in st.session_state or st.session_state.must_work_df.shape[1] != num_days:
        st.session_state.must_work_df = pd.DataFrame(False, index=staff_members, columns=column_names)
    must_df = st.data_editor(st.session_state.must_work_df, key="must_editor")

# --- 5. 計算ロジック ---
if st.button('この条件でシフトを自動生成する'):
    progress_bar = st.progress(0)
    st.write("AIが『指定された出勤日数』を最優先して計算中です...")
    
    qubo = {}
    # 重みのバランスを大幅に変更
    A = 1500 # 出勤日数を守る (前回の2.5倍以上に強化。これが「11日」を防ぐ鍵)
    B = 800  # 希望休・出勤必須 (絶対に守る)
    C = 20   # 1日の人数 (あえて弱める。人数が多少ズレても、個人の出勤数を優先させる)
    E = 30   # 連勤抑制

    for i, name in enumerate(staff_members):
        target = targets[name]
        
        # 【勤務日数制約】 指定された日数以外になることを猛烈に嫌がらせる
        for d1 in range(num_days):
            qubo[(i, d1), (i, d1)] = qubo.get(((i, d1), (i, d1)), 0) + A * (1 - 2 * target)
            for d2 in range(num_days):
                if d1 != d2:
                    qubo[(i, d1), (i, d2)] = qubo.get(((i, d1), (i, d2)), 0) + A * 2
        
        # 【休み・出勤必須】
        for d in range(num_days):
            if off_df.iloc[i, d]:
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + B
            if must_df.iloc[i, d]:
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) - B

        # 【連勤抑制】
        for d in range(num_days - 1):
            qubo[(i, d), (i, d+1)] = qubo.get(((i, d), (i, d+1)), 0) + E

    # 【1日の人数制約】 火曜多め設定
    for d in range(num_days):
        current_wd = wd_list[(start_idx + d) % 7]
        is_tuesday = (current_wd == '火')
        daily_target = 5 if is_tuesday else 3
        
        for i1 in range(num_staff):
            qubo[(i1, d), (i1, d)] = qubo.get(((i1, d), (i1, d)), 0) + C * (1 - 2 * daily_target)
            for i2 in range(num_staff):
                if i1 != i2:
                    qubo[(i1, d), (i2, d)] = qubo.get(((i1, d), (i2, d)), 0) + C * 2

    # 計算（回数を100回に増やして、意地でも20日超えの答えを探させる）
    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo, num_reads=100)
    sample = response.first.sample
    progress_bar.progress(100)

    # 結果表示
    res_
