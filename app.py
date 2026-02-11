import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

st.set_page_config(layout="wide")
st.title('AIシフト作成アプリ (週5勤務重視版)')

# --- 設定 ---
staff_members = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん']
num_days = st.sidebar.slider('日数を設定', 28, 31, 30)
days = [f'{d+1}' for d in range(num_days)]
num_staff = len(staff_members)

# --- 入力 UI ---
st.sidebar.header('個別設定')
four_day_staff = st.sidebar.selectbox('週4勤務の人は？', staff_members)

st.header('📅 希望休の入力')
if 'off_req_df' not in st.session_state:
    st.session_state.off_req_df = pd.DataFrame(False, index=staff_members, columns=days)
edited_df = st.data_editor(st.session_state.off_req_df, use_container_width=True)

# --- 計算ロジック ---
if st.button('1ヶ月分のシフトを自動生成する'):
    with st.spinner('計算中...'):
        qubo = {}
        
        # 重みの調整（ここが肝です）
        A = 100 # 月間勤務日数の重み（最強に設定）
        B = 150 # 希望休の重み（絶対に守る）
        C = 40  # 1日の最低人数の重み
        E = 60  # 連勤禁止の重み

        for i, name in enumerate(staff_members):
            # 目標出勤日数
            target = 17 if name == four_day_staff else 22
            
            # 1. 【出勤日数制約】 targetの日数ぴったり出勤させる
            for d in range(num_days):
                # 自己相互作用：出勤しやすさを調整
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + A * (1 - 2 * target)
                for d2 in range(num_days):
                    if d != d2:
                        # 2変数の相互作用：出勤しすぎ・休みすぎを抑制
                        qubo[(i, d), (i, d2)] = qubo.get(((i, d), (i, d2)), 0) + A * 2
            
            # 2. 【希望休制約】
            for d in range(num_days):
                if edited_df.iloc[i, d]:
                    qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + B

            # 3. 【5連勤以上禁止】 
            for d in range(num_days - 5):
                # 6日連続出勤にペナルティ（d日からd+5日の組み合わせ）
                for d_next in range(d + 1, d + 6):
                    qubo[(i, d), (i, d_next)] = qubo.get(((i, d), (i, d_next)), 0) + E

        # 4. 【1日の人数制約】 最低3人、火曜(d%7==1)は5人
        for d in range(num_days):
            is_tuesday = (d % 7 == 1)
            lower_limit = 5 if is_tuesday else 3
            
            for i1 in range(num_staff):
                # 人数が足りない場合のペナルティを工夫
                qubo[(i1, d), (i1, d)] += C * (1 - 2 * lower_limit)
                for i2 in range(num_staff):
                    if i1 != i2:
                        qubo[(i1, d), (i2, d)] += C * 2

        # OpenJijで計算
        sampler = oj.SASampler()
        # 計算回数を増やして精度を上げる
        response = sampler.sample_qubo(qubo, num_reads=30)
        sample = response.first.sample
        
        # 結果表示
        res = np.zeros((num_staff, num_days), dtype=str)
        for (i, d), val in sample.items():
            res[i, d] = '◯' if val == 1 else ' '
        
        result_df = pd.DataFrame(res, index=staff_members, columns=days)
        st.header('📋 生成されたシフト表')
        st.dataframe(result_df, use_container_width=True)
        
        # 出勤日数の確認
        st.subheader('各スタッフの出勤日数')
        work_days = {name: np.sum(res[i] == '◯') for i, name in enumerate(staff_members)}
        st.write(work_days)
