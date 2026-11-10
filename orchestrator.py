"""
main.py - Orquestrador do Pipeline de Dimensionamento SMP e Backhaul Seridó.
"""
import os
import sys

from src.etapa1_dimensionamento_trafego import executar_etapa1
from src.etapa2_cobertura import executar_etapa2
from src.etapa3_interferencia import executar_etapa3
from src.etapa4_geolocacao import executar_etapa4
from src.etapa5_topografia import executar_etapa5
from src.etapa6_microondas import executar_etapa6
from src.etapa7_exportador_uisp import executar_etapa7

def main():
    print("\n" + "#" * 80)
    print(" INICIANDO PIPELINE: PROJETO SMP SERIDÓ -> UISP DESIGN CENTER")
    print("#" * 80 + "\n")
    
    os.makedirs("outputs", exist_ok=True)
    
    # 1. Tráfego e Erlang B
    print("[1/7] Calculando tráfego e capacidade celular...")
    executar_etapa1()
    
    # 2. Balanço de Potência e Raio Celular
    print("\n[2/7] Calculando Link Budget SMP e raio de cobertura...")
    executar_etapa2("outputs/demanda_capacidade.json")
    
    # 3. Interferência Co-canal (S/I)
    print("\n[3/7] Validando relação S/I do cluster 4x3...")
    executar_etapa3()
    
    # 4. Alocação Geográfica dos Sítios e CCC
    print("\n[4/7] Georreferenciando ERBs urbanas e nó CCC...")
    executar_etapa4("outputs/dimensionamento_cobertura.json")
    
    # 5. Topografia, Curvatura, Fresnel e Repetidoras
    print("\n[5/7] Mapeando relevo, testando visada e inserindo repetidoras...")
    executar_etapa5("outputs/sites_candidatos.json")
    
    # 6. Otimização de Rádios e Antenas Ubiquiti
    print("\n[6/7] Dimensionando hardware por custo-benefício (airFiber)...")
    executar_etapa6("outputs/enlaces_validados.json")
    
    # 7. Exportação KML para Ubiquiti
    print("\n[7/7] Gerando arquivo KML final...")
    executar_etapa7(
        arquivo_sitios="outputs/todos_sitios.json",
        arquivo_enlaces="outputs/enlaces_com_antenas.json",
        saida_kml="outputs/backhaul_serido_uisp.kml"
    )
    
    # 8. Mapa interativo com a rede validada (regenera o HTML a cada execução)
    print("\n[8/8] Gerando mapa interativo com a rede validada...")
    import runpy
    runpy.run_path("mapa_interativo.py", run_name="__main__")

    print("\n" + "=" * 80)
    print(" PIPELINE CONCLUÍDO COM SUCESSO!")
    print(" Arquivo gerado: outputs/backhaul_serido_uisp.kml")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()