import streamlit as st
import numpy as np
import pandas as pd
import openjij as oj

# 画面の幅を広く使う設定
st.set_page_config(layout="wide", page_title="AIシフト作成アプリ")

st.title('📅 AIシフト作成アプリ')
st.write('7人のスタッフの1ヶ月分のシフトを自動生成します。')

# --- 1. 基本設定 ---
staff_members = ['Aさん', 'Bさん', 'Cさん', 'Dさん', 'Eさん', 'Fさん', 'Gさん']
num_days = st.sidebar.slider('日数を設定', 28, 31, 30)
days = [f'{d+1}' for d in range(num_days)]
num_staff = len(staff_members)

# --- 2. 個別設定 (サイドバー) ---
st.sidebar.header('個別ルール設定')
four_day_staff = st.sidebar.selectbox('週4勤務（月17日目標）の人を選択', staff_members)

# --- 3. 希望休の入力 (メイン画面) ---
st.header('1. 希望休を入力してください')
st.info('表のセルをクリックしてチェックを入れると「休み」として扱われます。')

if 'off_req_df' not in st.session_state:
    # 初期状態はすべて出勤（False）
    st.session_state.off_req_df = pd.DataFrame(False, index=staff_members, columns=days)

# 編集可能なテーブルを表示
edited_df = st.data_editor(st.session_state.off_req_df, use_container_width=True)

# --- 4. 計算ロジック ---
if st.button('この条件でシフトを自動生成する'):
    with st.spinner('量子アニーリング・シミュレーションで計算中...'):
        qubo = {}
        
        # 重みパラメータ（この数値を調整して精度を上げます）
        A = 120 # 月間勤務日数の厳守（最優先）
        B = 200 # 希望休（絶対に守る）
        C = 50  # 1日の必要人数の確保
        E = 100 # 5連勤以上の禁止

        for i, name in enumerate(staff_members):
            # 月間の目標出勤日数（週休2日なら月約22日）
            target = 17 if name == four_day_staff else 22
            
            # 【勤務日数制約】 指定した日数ぴったりになるように調整
            for d in range(num_days):
                qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + A * (1 - 2 * target)
                for d2 in range(num_days):
                    if d != d2:
                        qubo[(i, d), (i, d2)] = qubo.get(((i, d), (i, d2)), 0) + A * 2
            
            # 【希望休制約】 チェックがついた日は出勤させない
            for d in range(num_days):
                if edited_df.iloc[i, d]:
                    qubo[(i, d), (i, d)] = qubo.get(((i, d), (i, d)), 0) + B

            # 【連勤抑制】 6日間連続で出勤しようとするとペナルティ
            for d in range(num_days - 5):
                for d_next in range(d + 1, d + 6):
                    qubo[(i, d), (i, d_next)] = qubo.get(((i, d), (i, d_next)), 0) + E / 5

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
        # 読み込み回数を増やして精度を高める
        response = sampler.sample_qubo(qubo, num_reads=50)
        sample = response.first.sample
        
        # 結果を ◯ と 空白 に変換
        res_matrix = np.zeros((num_staff, num_days), dtype=str)
        for (i, d), val in sample.items():
            res_matrix[i, d] = '◯' if val == 1 else ' '
        
        # 結果の表示
        result_df = pd.DataFrame(res_matrix, index=staff_members, columns=days)
        st.header('2. 生成されたシフト表')
        st.dataframe(result_df, use_container_width=True)
        
        # 各スタッフの最終出勤日数を集計
        st.subheader('集計結果チェック')
        col1, col2 = st.columns(2)
        
        with col1:
            st.write('■ 個人の出勤日数')
            work_counts = {name: np.sum(res_matrix[i] == '◯') for i, name in enumerate(staff_members)}
            st.write(pd.Series(work_counts, name="出勤日数"))

        with col2:
            st.write('■ 日ごとの出勤人数')
            day_counts = [np.sum(res_matrix[:, d] == '◯') for d in range(num_days)]
            st.write(pd.Series(day_counts, index=days, name="人数").to_frame().T)

st.divider()
st.caption('Powered by OpenJij & Streamlit')
