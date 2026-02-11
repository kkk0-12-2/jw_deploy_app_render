import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

# 画面の幅を広く使う設定
st.set_page_config(layout="wide", page_title="AIシフト作成アプリ")

st.title('📅 AIシフト作成アプリ (出勤日数重視版)')
st.write('7人のスタッフの1ヶ月分のシフトを生成します。出勤日数が20〜22日になるよう調整済みです。')

# --- 1. 基本設定 ---
staff_members = ['中村', '長坂', '角谷', 'Dさん', '小森', '宮内', '仲村']
num_days = st.sidebar.slider('日数を設定', 28, 31, 30)
days = [f'{d+1}' for d in range(num_days)]
num_staff = len(staff_members)

# --- 2. 個別設定 (サイドバー) ---
st.sidebar.header('個別ルール設定')
four_day_staff = st.sidebar.selectbox('週4勤務（月17日目標）の人を選択', staff_members)

# --- 3. 希望休の入力 ---
st.header('1. 希望休を入力してください')
if 'off_req_df' not in st.session_state:
    # 初期状態はすべて出勤（False）
    st.session_state.off_req_df = pd.DataFrame(False, index=staff_members, columns=days)

edited_df = st.data_editor(st.session_state.off_req_df, use_container_width=True)

# --- 4. 計算ロジック ---
if st.button('この条件でシフトを自動生成する'):
    with st.spinner('AIが最適な出勤バランスを計算中です...'):
        qubo = {}
        
        # 重みパラメータの再調整（出勤日数を守らせるためにAを最強に設定）
        A = 500 # 月間勤務日数の厳守
        B = 400 # 希望休
        C = 30  # 1日の最低人数
        E = 50  # 連勤抑制

        for i, name in enumerate(staff_members):
            # 月間の目標出勤日数
            target = 17 if name == four_day_staff else 22
            
            # 【勤務日数制約】
            for d1 in range(num_days):
                qubo[(i, d1), (i, d1)] = qubo.get(((i, d1), (i, d1)), 0) + A * (1 - 2 * target)
                for d2 in range(num_days):
                    if d1 != d2:
                        qubo[(i, d1), (i, d2)] = qubo.get(((i, d1), (i, d2)), 0) + A * 2
            
            # 【希望休制約】
            for d in range(num_days):
                if edited_df.iloc[i, d]:
                    qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + B

            # 【連勤抑制】
            for d in range(num_days - 1):
                qubo[(i, d), (i, d+1)] = qubo.get(((i, d), (i, d+1)), 0) + E

        # 【1日の人数制約】 最低3人、火曜(d%7==1)は5人を目標
        for d in range(num_days):
            is_tuesday = (d % 7 == 1)
            daily_target = 5 if is_tuesday else 3
            
            for i1 in range(num_staff):
                qubo[(i1, d), (i1, d)] = qubo.get(((i1, d), (i1, d)), 0) + C * (1 - 2 * daily_target)
                for i2 in range(num_staff):
                    if i1 != i2:
                        qubo[(i1, d), (i2, d)] = qubo.get(((i1, d), (i2, d)), 0) + C * 2

        # OpenJijで計算を実行
        sampler = oj.SASampler()
        response = sampler.sample_qubo(qubo, num_reads=100)
        sample = response.first.sample
        
        # 結果を ◯ と 空白 に変換
        res_matrix = np.zeros((num_staff, num_days), dtype=str)
