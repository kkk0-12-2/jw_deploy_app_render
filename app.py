import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

# 画面設定
st.set_page_config(layout="wide", page_title="AIシフト作成アプリ")

st.title('📅 AIシフト作成アプリ')
st.write('スタッフ名更新、曜日表示、出勤必須日設定に対応しました。')

# --- 1. 基本設定 ---
# スタッフ名を指定の名前に更新
staff_members = ['中村', '長坂', '角谷', '小森', '宮内', '仲村']
num_days = st.sidebar.slider('日数を設定', 28, 31, 30)
num_staff = len(staff_members)

# 曜日を計算（1日が月曜日と仮定）
wdays = ['月', '火', '水', '木', '金', '土', '日']
column_names = [f"{d+1}({wdays[d % 7]})" for d in range(num_days)]

# --- 2. 個別設定 ---
st.sidebar.header('個別ルール設定')
four_day_staff = st.sidebar.selectbox('週4勤務の人を選択（他は週5目安）', staff_members)

# --- 3. 入力セクション ---
st.header('1. シフト条件の入力')
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader('❌ 希望休（休みを指示）')
    if 'off_req_df' not in st.session_state:
        st.session_state.off_req_df = pd.DataFrame(False, index=staff_members, columns=column_names)
    off_df = st.data_editor(st.session_state.off_req_df, key="off_editor")

with col_in2:
    st.subheader('✅ 出勤必須（必ず出る日を指示）')
    if 'must_work_df' not in st.session_state:
        st.session_state.must_work_df = pd.DataFrame(False, index=staff_members, columns=column_names)
    must_df = st.data_editor(st.session_state.must_work_df, key="must_editor")

# --- 4. 計算ロジック ---
if st.button('この条件でシフトを自動生成する'):
    progress_bar = st.progress(0)
    st.write("AIが最適な組み合わせを計算中です...")
    
    qubo = {}
    # 重み設定
    A = 500  # 勤務日数守る（最強）
    B = 400  # 希望休・出勤必須守る
    C = 60   # 1日の人数（火曜多め含む）
    E = 50   # 連勤抑制

    for i, name in enumerate(staff_members):
        target = 17 if name == four_day_staff else 22
        
        # 【勤務日数制約】
        for d1 in range(num_days):
            qubo[(i, d1), (i, d1)] = qubo.get(((i, d1), (i, d1)), 0) + A * (1 - 2 * target)
            for d2 in range(num_days):
                if d1 != d2:
                    qubo[(i, d1), (i, d2)] = qubo.get(((i, d1), (i, d2)), 0) + A * 2
        
        # 【休み・出勤必須の制約】
        for d in range(num_days):
            if off_df.iloc[i, d]: # 希望休なら出勤にペナルティ
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + B
            if must_df.iloc[i, d]: # 出勤必須なら「休むこと」にペナルティ
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) - B

        # 【連勤抑制】
        for d in range(num_days - 1):
            qubo[(i, d), (i, d+1)] = qubo.get(((i, d), (i, d+1)), 0) + E

    # 【1日の人数制約】 火曜(d%7==1)は会議のため多め
    for d in range(num_days):
        is_tuesday = (d % 7 == 1)
        daily_target = 5 if is_tuesday else 3 # 火曜5人、他3人
        
        for i1 in range(num_staff):
            qubo[(i1, d), (i1, d)] = qubo.get(((i1, d), (i1, d)), 0) + C * (1 - 2 * daily_target)
            for i2 in range(num_staff):
                if i1 != i2:
                    qubo[(i1, d), (i2, d)] = qubo.get(((i1, d), (i2, d)), 0) + C * 2

    # 計算
    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo, num_reads=50)
    sample = response.first.sample
    progress_bar.progress(100)

    # 結果表示
    res_matrix = np.zeros((num_staff, num_days), dtype=str)
    for (i, d), val in sample.items():
        res_matrix[i, d] = '◯' if val == 1 else ' '
    
    result_df = pd.DataFrame(res_matrix, index=staff_members, columns=column_names)
    st.header('2. 生成されたシフト表')
    st.dataframe(result_df, width=1500)
    
    # 集計
    st.subheader('集計結果')
    c1, c2 = st.columns(2)
    with c1:
        st.write('■ スタッフ別出勤日数')
        counts = {n: np.sum(res_matrix[i] == '◯') for i, n in enumerate(staff_members)}
        st.write(pd.Series(counts))
    with c2:
        st.write('■ 日別出勤人数')
        d_counts = [np.sum(res_matrix[:, d] == '◯') for d in range(num_days)]
        st.write(pd.Series(d_counts, index=column_names).to_frame().T)
