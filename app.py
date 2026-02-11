import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

st.set_page_config(layout="wide") # 画面を広く使う
st.title('AIシフト作成アプリ (1ヶ月対応版)')

# --- 設定 ---
staff_members = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん']
num_days = st.sidebar.slider('日数を設定', 28, 31, 30)
days = [f'{d+1}' for d in range(num_days)]
num_staff = len(staff_members)

# --- 入力 UI ---
st.sidebar.header('個別設定')
four_day_staff = st.sidebar.selectbox('週4勤務(月16-17日)の人は？', staff_members)

st.header('📅 希望休の入力（1ヶ月分）')
st.info('休みを希望する日にチェックを入れてください。')

# 希望休入力用のデータフレーム作成
if 'off_req_df' not in st.session_state:
    st.session_state.off_req_df = pd.DataFrame(False, index=staff_members, columns=days)

# 編集可能なテーブルとして表示
edited_df = st.data_editor(st.session_state.off_req_df, use_container_width=True)

# --- 計算ロジック ---
if st.button('1ヶ月分のシフトを自動生成する'):
    with st.spinner('AIが最適な組み合わせを計算中...'):
        qubo = {}
        
        # 重み設定
        A = 50  # 勤務日数
        B = 100 # 希望休
        C = 30  # 1日の最低人数
        D = 10  # 火曜日優先
        
        for i, name in enumerate(staff_members):
            # 目標月間勤務日数 (週4なら17日、週5なら22日程度)
            target = 17 if name == four_day_staff else 22
            
            # 1. 月間勤務日数制約
            for d1 in range(num_days):
                qubo[(i, d1), (i, d1)] = qubo.get(((i, d1), (i, d1)), 0) + A * (1 - 2 * target)
                for d2 in range(num_days):
                    if d1 != d2:
                        qubo[(i, d1), (i, d2)] = qubo.get(((i, d1), (i, d2)), 0) + A * 2
            
            # 2. 希望休制約
            for d in range(num_days):
                if edited_df.iloc[i, d]:
                    qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + B

        # 3. 1日の人数制約（毎日最低3人、火曜日はもっと欲しい）
        for d in range(num_days):
            # 火曜日(0日目が月曜と仮定した場合、1, 8, 15, 22...が火曜)
            is_tuesday = (d % 7 == 1) 
            daily_target = 5 if is_tuesday else 3 # 火曜は5人、他は3人を目標
            
            for i1 in range(num_staff):
                qubo[(i1, d), (i1, d)] = qubo.get(((i1, d), (i1, d)), 0) + C * (1 - 2 * daily_target)
                for i2 in range(num_staff):
                    if i1 != i2:
                        qubo[(i1, d), (i2, d)] = qubo.get(((i1, d), (i2, d)), 0) + C * 2

        # 4. 5連勤禁止（簡易的なペナルティ）
        for i in range(num_staff):
            for d in range(num_days - 5):
                # 6連続で1になるとペナルティ
                # (本来は高次項ですが、近似的に隣接2変数のペナルティを強化)
                qubo[(i, d), (i, d+1)] = qubo.get(((i, d), (i, d+1)), 0) + 5

        # 計算実行
        sampler = oj.SASampler()
        response = sampler.sample_qubo(qubo, num_reads=10)
        sample = response.first.sample
        
        # 結果整形
        res = np.zeros((num_staff, num_days), dtype=str)
        for (i, d), val in sample.items():
            res[i, d] = '◯' if val == 1 else ' '
        
        result_df = pd.DataFrame(res, index=staff_members, columns=days)
        st.header('📋 生成された1ヶ月シフト表')
        st.dataframe(result_df, use_container_width=True)
        
        #
