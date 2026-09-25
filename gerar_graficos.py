#!/usr/bin/env python3
"""
Autor: Lucas Rohr Carreno
Script de Geração de Gráficos de Desempenho de Protocolos de Roteamento (OSPF, RIP, BGP)
"""

import pandas as pd
import matplotlib.pyplot as plt
import os

# Configuração visual dos gráficos
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10

def carregar_dados(csv_file="metricas_desempenho.csv"):
    if not os.path.exists(csv_file):
        print(f"[ERROR] Arquivo {csv_file} não encontrado.")
        return None
    df = pd.read_csv(csv_file)
    # Converte colunas numéricas
    df['RTT_Medio_ms'] = pd.to_numeric(df['RTT_Medio_ms'])
    df['CPU_Router1_Pct'] = pd.to_numeric(df['CPU_Router1_Pct'])
    df['RAM_Router1_MB'] = pd.to_numeric(df['RAM_Router1_MB'])
    df['Total_Pacotes_R1'] = pd.to_numeric(df['Total_Pacotes_R1'])
    df['Total_Bytes_R1'] = pd.to_numeric(df['Total_Bytes_R1'])
    df['Total_KB_R1'] = df['Total_Bytes_R1'] / 1024
    return df

def gerar_grafico_rtt(df):
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(df['Protocolo'], df['RTT_Medio_ms'], color='#1f77b4', edgecolor='black', width=0.5)
    
    ax.set_title('Comparativo de Latência Média (RTT) por Protocolo', fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel('Cenário / Protocolo', fontweight='bold')
    ax.set_ylabel('RTT Médio (ms)', fontweight='bold')
    ax.set_ylim(0, max(df['RTT_Medio_ms']) * 1.25)

    # Adiciona rótulos de valor no topo das barras
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 0.005, f'{yval:.3f} ms', ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    plt.savefig('grafico_rtt_comparativo.png', dpi=300)
    plt.close()
    print("[✔] Gráfico gerado: grafico_rtt_comparativo.png")

def gerar_grafico_overhead(df):
    fig, ax1 = plt.subplots(figsize=(9, 5))

    color_pkts = '#2ca02c'
    color_bytes = '#ff7f0e'

    x = range(len(df['Protocolo']))
    width = 0.35

    rects1 = ax1.bar([i - width/2 for i in x], df['Total_Pacotes_R1'], width, label='Total de Pacotes', color=color_pkts, edgecolor='black')
    ax1.set_xlabel('Cenário / Protocolo', fontweight='bold')
    ax1.set_ylabel('Total de Pacotes (RX + TX)', color=color_pkts, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor=color_pkts)
    ax1.set_xticks(x)
    ax1.set_xticklabels(df['Protocolo'])

    ax2 = ax1.twinx()
    rects2 = ax2.bar([i + width/2 for i in x], df['Total_KB_R1'], width, label='Volume (KB)', color=color_bytes, edgecolor='black')
    ax2.set_ylabel('Volume de Dados (KB)', color=color_bytes, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor=color_bytes)

    # Rótulos nas barras
    for bar in rects1:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10, f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=8, color=color_pkts, fontweight='bold')
    for bar in rects2:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{bar.get_height():.1f} KB', ha='center', va='bottom', fontsize=8, color=color_bytes, fontweight='bold')

    plt.title('Overhead de Tráfego de Controle e Dados por Protocolo', fontsize=12, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig('grafico_overhead_trafego.png', dpi=300)
    plt.close()
    print("[✔] Gráfico gerado: grafico_overhead_trafego.png")

def gerar_grafico_hardware(df):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # CPU
    bars1 = ax1.bar(df['Protocolo'], df['CPU_Router1_Pct'], color='#d62728', edgecolor='black', width=0.5)
    ax1.set_title('Uso de CPU no Roteador 1 (%)', fontweight='bold')
    ax1.set_ylabel('CPU (%)', fontweight='bold')
    ax1.set_ylim(0, max(df['CPU_Router1_Pct']) * 1.3 if max(df['CPU_Router1_Pct']) > 0 else 1)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 0.01, f'{yval:.2f}%', ha='center', va='bottom', fontsize=9)

    # RAM
    bars2 = ax2.bar(df['Protocolo'], df['RAM_Router1_MB'], color='#9467bd', edgecolor='black', width=0.5)
    ax2.set_title('Uso de Memória RAM no Roteador 1 (MB)', fontweight='bold')
    ax2.set_ylabel('RAM (MB)', fontweight='bold')
    ax2.set_ylim(min(df['RAM_Router1_MB']) * 0.9, max(df['RAM_Router1_MB']) * 1.1)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + 0.1, f'{yval:.2f} MB', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig('grafico_consumo_hardware.png', dpi=300)
    plt.close()
    print("[✔] Gráfico gerado: grafico_consumo_hardware.png")

def main():
    df = carregar_dados()
    if df is not None:
        gerar_grafico_rtt(df)
        gerar_grafico_overhead(df)
        gerar_grafico_hardware(df)
        print("\n[✔] Todos os gráficos foram gerados e salvos com sucesso no diretório corrente!")

if __name__ == "__main__":
    main()