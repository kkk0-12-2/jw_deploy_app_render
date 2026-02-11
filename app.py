import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

st.set_page_config(layout="wide", page_title="AIシフト作成アプリ")

st.title('📅 AIシフト作成アプリ (平日ほぼ全員出勤版)')

# --- 1. 基本設定 ---
staff_members = ['中村', '長坂', '角谷', '小森', '宮内', '仲村']
num_staff = len(staff_members)

# --- 2. カレンダー設定 ---
st.sidebar.header('📅 カレンダー設定')
num_days = st.sidebar.slider('今月の日数', 28, 31, 30)
start_wd = st.sidebar.selectbox('今月の1日は何曜日？', ['月', '火', '水', '木', '金', '土', '日'])
wd_list = ['月', '火', '水', '木', '金', '土', '日']
start_idx = wd_list.index(start_wd)

simple_columns = [f"{d+1}" for d in range(num_days)]
st.info(f"設定確認：火曜は【全員】、他平日は【5人】、土日は【1人】を目標にします。※希望休は最優先されます。")

# --- 3. 出勤日数の個別指定 ---
st.sidebar.header('👤 スタッフ別・目標出勤日数')
targets = {}
for name in staff_members:
    targets[name] = st.sidebar.slider(f'{name}さんの目標日数', 15, 26, 22)

# --- 4. 入力セクション ---
st.header('1. 条件の入力')
col_in1, col_in2 = st.columns(2)

if 'off_req_df' not in st.session_state or st.session_state.off_req_df.shape[1] != num_days:
    st.session_state.off_req_df = pd.DataFrame(False, index=staff_members, columns=simple_columns)
if 'must_work_df' not in st.session_state or st.session_state.must_work_df.shape[1] != num_days:
    st.session_state.must_work_df = pd.DataFrame(False, index=staff_members, columns=simple_columns)

with col_in1:
    st.subheader('❌ 希望休 (休み)')
    off_df = st.data_editor(st.session_state.off_req_df, key="off_editor")

with col_in2:
    st.subheader('✅ 出勤必須 (必ず出る)')
    must_df = st.data_editor(st.session_state.must_work_df, key="must_editor")

# --- 5. 計算ロジック ---
if st.button('この条件でシフトを自動生成する'):
    progress_bar = st.progress(0)
    
    qubo = {}
    # 重みの設定
    A = 4000  # 出勤日数を守る (超最強)
    B = 2000  # 希望休 (Aより強くすることで、出勤日数を守りつつも休みを優先させる)
    C = 100   # 人数制約
    E = 10    # 連勤抑制 (今回は出勤を詰めたいので弱めに設定)

    for i, name in enumerate(staff_members):
        target = targets[name]
        # 【勤務日数制約】
        for d1 in range(num_days):
            qubo[(i, d1), (i, d1)] = qubo.get(((i, d1), (i, d1)), 0) + A * (1 - 2 * target)
            for d2 in range(num_days):
                if d1 != d2:
                    qubo[(i, d1), (i, d2)] = qubo.get(((i, d1), (i, d2)), 0) + A * 2
        
        # 【休み・出勤必須】
        for d in range(num_days):
            if off_df.iloc[i, d]:
                # 希望休はBの重みで「出勤すること」に大きな罰金
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + B
            if must_df.iloc[i, d]:
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) - B

    # 【1日の人数制約】
    for d in range(num_days):
        current_wd = wd_list[(start_idx + d) % 7]
        
        if current_wd in ['土', '日']:
            daily_target = 1  # 土日は1人
        elif current_wd == '火':
            daily_target = num_staff  # 火曜日は全員(6人)
        else:
            daily_target = 5  # 他の平日は5人 (ほぼ全員)
            
        for i1 in range(num_staff):
            qubo[(i1, d), (i1, d)] = qubo.get(((i1, d), (i1, d)), 0) + C * (1 - 2 * daily_target)
            for i2 in range(num_staff):
                if i1 != i2:
                    qubo[(i1, d), (i2, d)] = qubo.get(((i1, d), (i2, d)), 0) + C * 2

    # 計算
    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo, num_reads=150)
    sample = response.first.sample
    progress_bar.progress(100)

    # 結果表示
    column_with_wd = [f"{d+1}({wd_list[(start_idx + d) % 7]})" for d in range(num_days)]
    res_matrix = np.zeros((num_staff, num_days), dtype=str)
    for (i, d), val in sample.items():
        res_matrix[i, d] = '◯' if val == 1 else ' '
    
    result_df = pd.DataFrame(res_matrix, index=staff_members, columns=column_with_wd)
    st.header('2. 生成されたシフト表')
    st.dataframe(result_df, width=1500)
    
    st.subheader('集計結果チェック')
    c1, c2 = st.columns(2)
    with c1:
        st.write('■ スタッフ別出勤日数')
        counts = {n: np.sum(res_matrix[i] == '◯') for i, n in enumerate(staff_members)}
        st.write(pd.Series(counts))
    with c2:
        st.write('■ 日別出勤人数')
        d_counts = [np.sum(res_matrix[:, d] == '◯') for d in range(num_days)]
        st.write(pd.Series(d_counts, index=column_with_wd).to_frame().T)
