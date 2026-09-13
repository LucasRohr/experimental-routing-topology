#!/usr/bin/env python3
import subprocess
import json
import time
import csv
import sys
import argparse

def exec_cmd(cmd):
    """Executa comandos no shell do hospedeiro e retorna a saída."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_routing_table_size(router_name):
    """Extrai a quantidade exata de rotas ativas na FIB/RIB do roteador"""
    cmd = f"sudo docker exec {router_name} vtysh -c 'show ip route json'"
    raw_output = exec_cmd(cmd)
    try:
        data = json.loads(raw_output)
        return len(data)
    except Exception:
        # Fallback para parsing em texto quando o JSON não estiver disponível
        cmd_text = f"sudo docker exec {router_name} vtysh -c 'show ip route' | grep -E '^(O|B|R|C|K)' | wc -l"
        return int(exec_cmd(cmd_text) or 0)

def measure_rtt(source_router, target_ip, count=10):
    """Mede a latência média (RTT) e perda de pacotes via ICMP"""
    cmd = f"sudo docker exec {source_router} ping -c {count} -i 0.2 {target_ip}"
    output = exec_cmd(cmd)
    
    loss = 100.0 ## Inicializa perda de pacotes como 100% caso não haja resposta
    avg_rtt = 0.0 ## Inicializa RTT médio como 0.0 caso não haja resposta
    
    for line in output.split('\n'):
        if 'packet loss' in line:
            parts = line.split(',')
            for part in parts:
                if 'packet loss' in part:
                    # Extrai a porcentagem de perda de pacotes
                    loss = float(part.split('%')[0].strip().split()[-1])
        if 'rtt min/avg/max' in line or 'round-trip min/avg/max' in line:
            stats = line.split('=')[1].strip().split('/')[1]
            avg_rtt = float(stats) # Converte para float e armazena o RTT médio
            
    return avg_rtt, loss

# Função para medir o consumo de hardware do container Docker
def get_container_resources(container_name):
    """Coleta o percentual de uso de CPU e o consumo de memória RAM (em MB) do roteador"""
    cmd = f"sudo docker stats --no-stream --format '{{{{.CPUPerc}}}};{{{{.MemUsage}}}}' {container_name}"
    output = exec_cmd(cmd)
    try:
        cpu_str, mem_str = output.split(';')
        cpu_val = float(cpu_str.replace('%', '').strip())
        
        # Extrai e converte o uso absoluto de memória RAM para megabytes
        used_mem = mem_str.split('/')[0].strip()
        if 'GiB' in used_mem:
            mem_mb = float(used_mem.replace('GiB', '').strip()) * 1024
        else:
            mem_mb = float(used_mem.replace('MiB', '').replace('B', '').strip())
        return cpu_val, mem_mb
    except Exception:
        return 0.0, 0.0

# Função para monitorar a quantidade e volume de pacotes de controle/dados
def get_network_traffic_stats(container_name):
    """Lê /proc/net/dev do container para capturar pacotes e bytes acumulados nas interfaces"""
    cmd = f"sudo docker exec {container_name} cat /proc/net/dev"
    output = exec_cmd(cmd)
    total_packets = 0
    total_bytes = 0
    for line in output.split('\n'):
        if ':' in line and not line.strip().startswith('lo'):
            parts = line.split(':')[1].split()
            rx_bytes, rx_pkts = int(parts[0]), int(parts[1])
            tx_bytes, tx_pkts = int(parts[8]), int(parts[9])
            total_bytes += (rx_bytes + tx_bytes)
            total_packets += (rx_pkts + tx_pkts)
    return total_packets, total_bytes

def simulate_failure_and_measure_convergence(primary_link_net, test_router, target_ip):
    """
    Derruba uma rede de enlace no Docker e mede o tempo (em segundos) até que o tráfego se restabeleça pelo caminho alternativo
    """
    print(f"[!] Injetando falha no enlace: {primary_link_net}...")
    
    # Inicia medição de tempo
    start_time = time.time()
    
    # Desconecta o link no Docker
    exec_cmd(f"sudo docker network disconnect {primary_link_net} router1")
    
    convergence_time = None
    timeout = 30.0 # Tempo máximo de espera para convergência
    
    while (time.time() - start_time) < timeout:
        # Tenta ping único com timeout curto de 200ms
        cmd = f"sudo docker exec {test_router} ping -c 1 -W 1 {target_ip}"
        res = exec_cmd(cmd)
        if "1 packets transmitted, 1 received" in res or "1 received" in res:
            convergence_time = time.time() - start_time
            break
        time.sleep(0.1)
        
    print(f"[+] Reestabelecendo o enlace: {primary_link_net}...")
    exec_cmd(f"sudo docker network connect {primary_link_net} router1 --ip 172.25.13.2")
    
    # Tempo para estabilização pós-reconexão
    time.sleep(5)
    
    return convergence_time if convergence_time else timeout

def main():
    parser = argparse.ArgumentParser(description="Coletor de Métricas de Roteamento")
    # Argumento obrigatório para especificar o protocolo sob teste
    # Opções válidas: OSPF, RIP, BGP_ONLY
    parser.add_argument("--protocol", required=True, choices=["OSPF", "RIP", "BGP_ONLY"], help="Nome do protocolo sob teste")
    args = parser.parse_args()

    print(f"=== INICIANDO BATERIA DE TESTES: PROTOCOLO {args.protocol} ===")
    
    # 1. Tamanho da Tabela de Roteamento
    table_size_r1 = get_routing_table_size("router1")
    table_size_r5 = get_routing_table_size("router5")
    print(f"[*] Tamanho Tabela Roteamento (Router 1): {table_size_r1} entradas")
    print(f"[*] Tamanho Tabela Roteamento (Router 5): {table_size_r5} entradas")

    # 2. Medição de Delay (RTT) e Perda de Pacotes
    target_destination = "10.30.0.2" # Endereço IP destino no AS 300
    rtt, loss = measure_rtt("router1", target_destination, count=20)
    print(f"[*] RTT Médio (R1 -> R5 LAN): {rtt:.3f} ms")
    print(f"[*] Perda de Pacotes Inicial: {loss:.1f}%")

    # 3. Coleta de Consumo de Hardware
    cpu_r1, mem_r1 = get_container_resources("router1")
    print(f"[*] Consumo Hardware (Router 1): CPU = {cpu_r1:.2f}%, RAM = {mem_r1:.2f} MB")

    # 4. Coleta de Tráfego de Rede
    pkts_r1, bytes_r1 = get_network_traffic_stats("router1")
    print(f"[*] Tráfego de Rede (Router 1): {pkts_r1} pacotes, {bytes_r1 / 1024:.2f} KB")

    # 5. Teste de Convergência (Simulação de Falha do Link Direto AS100-AS300)
    # A rede BGP direta entre R1 e R5 é 'topologia_net-bgp-100-300'
    link_to_fail = "topologia_net-bgp-100-300"
    conv_time = simulate_failure_and_measure_convergence(link_to_fail, "router1", target_destination)
    print(f"[*] Tempo de Convergência pós-falha: {conv_time:.2f} segundos")

    # 6. Exportação dos Dados para CSV (para alimentar os gráficos do trabalho)
    csv_file = "metricas_desempenho.csv"
    file_exists = False
    try:
        with open(csv_file, "r"): file_exists = True
    except FileNotFoundError:
        pass

    with open(csv_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            # Cabeçalho cobrindo métricas de controle e hardware
            writer.writerow([
                "Protocolo", 
                "Tabela_R1_Entradas", 
                "RTT_Medio_ms", 
                "Perda_Pacotes_Pct", 
                "CPU_Router1_Pct", 
                "RAM_Router1_MB", 
                "Total_Pacotes_R1", 
                "Total_Bytes_R1", 
                "Tempo_Convergencia_s"
            ])
        writer.writerow([
            args.protocol, 
            table_size_r1, 
            rtt, 
            loss, 
            cpu_r1, 
            mem_r1, 
            pkts_r1, 
            bytes_r1, 
            f"{conv_time:.2f}"
        ])

    print(f"[✔] Resultados salvos com sucesso em {csv_file}\n")

if __name__ == "__main__":
    main()