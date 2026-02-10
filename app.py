import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import openjij as oj

#テキスト表示
st.title('都市を選択して巡回セールスマン問題を実施')
st.write('巡回する都市を選択してOpenJijで最適なルートを計算')

#サイドバー設定
with st.sidebar:
    st.write('計算のパラメーター設定')
    time_calc = st.number_input('タイムアウト時間',max_value = 10000, value = 1000, step = 1000)

#都市を設定
cities = {
    'A': [23, 56], 'B': [12, 24], 'C': [36, 72], 'D': [9, 53], 'E': [61, 55],
    'F': [47, 19], 'G': [33, 68]}

cities_list = list(cities.keys())

col1, col2 = st.columns(2) #横並びレイアウトを作成

with col1:
    #都市を選択
    selected_cities = st.multiselect('都市を選択',cities_list,default = cities_list)
with col2:
    import numpy as np
    import matplotlib.pyplot as plt

    if selected_cities:  # 都市が選択されている場合
        #選択した都市の座標をndarrayにする
        selected_coords = np.array([cities[pref] for pref in selected_cities])
        N = selected_coords.shape[0]  # 都市数

        # 都市の座標をグラフで表示
        plt.figure(figsize=(7, 7))
        plt.plot(selected_coords[:, 0], selected_coords[:, 1], 'o')
        st.pyplot(plt)
    else:  # 都市が選択されていない場合
        selected_coords = np.array([])  # 空のndarrayをセット
        N = 0

        # 空のグラフを表示
        plt.figure(figsize=(7, 7))
        plt.title('No selected')
        st.pyplot(plt)

button1 = st.button('SQAを実行') #ボタンを作成
if button1:
    # 都市間の距離行列を作成
    x = selected_coords[:, 0]
    y = selected_coords[:, 1]
    d = np.sqrt((x[:, np.newaxis] - x[np.newaxis, :]) ** 2 +(y[:, np.newaxis] - y[np.newaxis, :]) ** 2)

    # 定式化
    def tsp_qubo(distance, A, B):
        n = len(distance)
        qubo = {}
    
        # コスト項 (巡回路の距離)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                for t in range(n):
                    qubo[(i, t), (j, (t+1) % n)] = distance[i, j]
    
        # 罰則項
        for i in range(n):
            for t in range(n):
                for k in range(t+1, n):
                    qubo[(i, t), (i, k)] = 2*A  # 同じ都市が複数回選ばれるのを防ぐ
    
                for j in range(i+1, n):
                    qubo[(i, t), (j, t)] = 2*B  # 1つの時刻に複数の都市が選ばれるのを防ぐ
    
                qubo[(i, t), (i, t)] = - A - B  # 自己制約を適用
    
        constant = n*(A + B)
        return qubo, constant
    
    # 重みの設定
    A = np.max(d) * 1.5
    B = np.max(d) * 1.5
    qubo, constant = tsp_qubo(d, A, B)

    # OpenJijのサンプラーで解く
    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo, num_reads=10)

    # 結果を表示
    def tsp_decode_sample(sample, n):
        """サンプルから巡回路を復元"""
        ones = [k for k, v in sample.items() if v == 1]
    
        # 取得された経路を行列化
        x_value = np.zeros((n, n), dtype=int)
        for i, t in ones:
            x_value[i, t] = 1
    
        # 制約違反をチェック
        condition_A = np.sum((np.sum(x_value, axis=1) - 1)**2)
        condition_B = np.sum((np.sum(x_value, axis=0) - 1)**2)
    
        # 経路を復元
        tour = np.zeros(n, dtype=int)
        for t in range(n):
            tour[t] = np.where(x_value[:, t] == 1)[0][0]
    
        return x_value, tour, {"condition_A": condition_A, "condition_B": condition_B}
    
    # 最適解をデコード
    sample = response.first.sample  # 最もエネルギーの低い解
    x_value, tour, violation = tsp_decode_sample(sample, N)
    total_distance = sum(d[tour[i]][tour[(i+1)%N]] for i in range(N))
    st.write(f'総距離:{total_distance}')
    
    # 巡回路の可視化
    plt.figure(figsize=(7, 7))
    plt.plot(x, y, "o")
    plt.plot(x[tour], y[tour], "-")
    plt.plot(x[[tour[-1], tour[0]]], y[[tour[-1], tour[0]]], "-")
    st.pyplot(plt)
