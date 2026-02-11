import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

st.title('AIシフト作成アプリ (プロトタイプ)')
st.write('7人のスタッフの1週間分のシフトを自動生成します。')

# --- 設定 ---
staff_members = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん']
days = ['月', '火', '水', '木', '金', '土', '日']
num_staff = len(staff_members)
num_days = len(days)

# --- 入力 UI ---
st.sidebar.header('個別設定')
four_day_staff = st.sidebar.selectbox('週4勤務の人は？', staff_members)

st.header('希望休の入力')
st.write('休みを希望する日にチェックを入れてください。')

# 希望休を保持する行列 (行=人, 列=日)
off_requests = np.zeros((num_staff, num_days))
cols = st.columns(num_days)
for j, day in enumerate(days):
    with cols[j]:
        st.write(day)
        for i, name in enumerate(staff_members):
            if st.checkbox(f'{name}', key=f'{i}-{j}'):
                off_requests[i, j] = 1

# --- 計算ロジック (QUBO) ---
if st.button('シフトを自動生成する'):
    # QUBOの作成
    qubo = {}
    
    # 制約の重み
    A = 50  # 勤務日数の制約
    B = 100 # 希望休の制約
    
    for i, name in enumerate(staff_members):
        # 目標勤務日数
        target = 4 if name == four_day_staff else 5
        
        # 1. 勤務日数制約: (Σx_ij - target)^2
        for j1 in range(num_days):
            qubo[(i, j1), (i, j1)] = qubo.get(((i, j1), (i, j1)), 0) + A * (1 - 2 * target)
            for j2 in range(num_days):
                if j1 != j2:
                    qubo[(i, j1), (i, j2)] = qubo.get(((i, j1), (i, j2)), 0) + A * 2
        
        # 2. 希望休制約: 希望休の日に働くと罰則
        for j in range(num_days):
            if off_requests[i, j] == 1:
                qubo[(i, j), (i, j)] = qubo.get(((i, j), (i, j)), 0) + B

    # OpenJij で計算
    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo, num_reads=10)
    sample = response.first.sample
    
    # 結果の整形
    result_matrix = np.zeros((num_staff, num_days), dtype=str)
    for (i, j), val in sample.items():
        result_matrix[i, j] = '◯' if val == 1 else '×'
    
    # 表として表示
    df = pd.DataFrame(result_matrix, index=staff_members, columns=days)
    st.header('生成されたシフト表')
    st.table(df)
    st.write('◯: 出勤, ×: 休み')
