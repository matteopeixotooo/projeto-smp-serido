"""src/config.py - Constantes globais e parâmetros normativos do Projeto 07."""

# Parâmetros de Radiofrequência SMP (Celular)
FREQ_SMP_MHZ = 1800.0  # Faixa de 1.800 MHz
BW_CANAL_RF_KHZ = 200.0  # Banda de 200 kHz por canal de RF
TIME_SLOTS_POR_RF = 8  # 8 time slots por portadora de RF

# Potências e Ganhos
POT_TX_ERB_W = 10.0  # 10 W de potência de transmissão na ERB
POT_TX_EM_W = 0.8  # 0,8 W de potência de transmissão na EM
GANHO_ANTENA_ERB_DBI = 18.0  # Ganho da antena setorial na ERB
GANHO_ANTENA_EM_DBI = 0.0  # Ganho da antena omni na EM
LIMIAR_RX_ERB_DBM = -105.0  # Sensibilidade de recepção na ERB
LIMIAR_RX_EM_DBM = -102.0  # Sensibilidade típica de recepção na EM móvel

# Restrições Estruturais e Topológicas
ALTURA_MAX_TORRE_M = 100.0  # Torres com até 100 metros de altura
ALTURA_PADRAO_ERB_M = 45.0  # Altura nominal típica adotada para a ERB
ALTURA_EM_M = 1.5  # Altura padrão do telemóvel do utilizador
CLUSTER_K = 4  # Cluster com 4 ERBs (configuração 4x3)
SETORES_POR_ERB = 3  # 3 células setorizadas por ERB
MAX_CANAIS_RF_SETOR = 8  # Máximo de 8 canais de RF por setor[cite: 1]

# Tráfego e Requisitos de Qualidade
TRAFEGO_USUARIO_ERL = 0.015  # 0,015 Erlang por assinante[cite: 1]
NUM_CONCORRENTES = 2  # 2 empresas concorrendo com a sua[cite: 1]
FRACAO_MERCADO = 1.0 / (NUM_CONCORRENTES + 1)
EXIGENCIA_SI_MIN_DB = 12.0  # S/I > 12 dB exigido no pior caso[cite: 1]

# Perdas Adicionais de RF (Cabos, Conectores, Corpo do Utilizador)
PERDAS_CABO_ERB_DB = 2.0
PERDAS_CORPO_EM_DB = 1.5
MARGEM_SOMBREAMENTO_DB = 6.0  # Margem Log-normal para desvanecimento lento (Slow Fading)