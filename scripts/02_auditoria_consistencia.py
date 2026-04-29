"""
02 - Auditoria de consistência entre planilha de álcool e Arruda Super Base
==========================================================================
Para os 130 linkados, comparar:
  - Sexo (planilha 1=M, 2=F  vs  Arruda M/F)
  - Idade vs IDADE_CIRURGIA + tempo cirurgia
  - IMC_pre planilha vs IMC_PRE Arruda
  - Tempo_cir (meses) consistente com (data atual - DATA_CIRURGIA)?

Saída:
  trabalho/resultados/02_auditoria_consistencia.md
  trabalho/dados/AUDITORIA_FLAGS.csv
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np
from datetime import datetime, timedelta

cw = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/CROSSWALK_ALCOOL_ARRUDA.csv',
                 low_memory=False)
print(f'Linkados: {len(cw)}')

def parse_date(x):
    if pd.isna(x): return None
    s = str(x).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d','%d/%m/%Y','%d/%m/%y','%Y-%m-%dT%H:%M:%S'):
        try: return datetime.strptime(s, fmt)
        except: pass
    return None

cw['DT_CIR'] = cw['DATA_CIRURGIA'].apply(parse_date)
cw['DT_NASC'] = cw['DATANASCIMENTO'].apply(parse_date)

# === Sexo ===
# Planilha: Sexo: 1=M, 2=F
# Arruda: SEXO 'M' ou 'F'
def sexo_alc(v):
    if pd.isna(v): return None
    s = str(v).strip().upper()
    if s in ('1','M','MASC','MASCULINO'): return 'M'
    if s in ('2','F','FEM','FEMININO'): return 'F'
    return None

cw['SEXO_ALC'] = cw['Sexo:'].apply(sexo_alc)
cw['SEXO_ARR'] = cw['SEXO'].astype(str).str.strip().str.upper().str[0]

sexo_match = (cw['SEXO_ALC'] == cw['SEXO_ARR'])
sexo_disc = cw[(cw['SEXO_ALC'].notna()) & (cw['SEXO_ARR'].notna()) & ~sexo_match]
print(f'\n=== SEXO ===')
print(f'  Concordantes: {sexo_match.sum()}/{len(cw)}')
print(f'  Discordantes: {len(sexo_disc)}')
if len(sexo_disc) > 0:
    print(sexo_disc[['NOME_ALC','SEXO_ALC','SEXO_ARR','NOME_ARRUDA_FULL']].to_string())

# === Idade vs IDADE_CIRURGIA + tempo cirurgia ===
# IDADE planilha = idade ATUAL (no momento do questionário)
# IDADE_CIRURGIA Arruda + Tempo_cir (meses) deveria dar idade atual aproximada
cw['IDADE_ALC'] = pd.to_numeric(cw['IDADE'], errors='coerce')
cw['TEMPO_CIR_MESES'] = pd.to_numeric(cw['Tempo_cir'], errors='coerce')
cw['IDADE_CIR_ARR'] = pd.to_numeric(cw['IDADE_CIRURGIA'], errors='coerce')

cw['IDADE_ESTIMADA'] = cw['IDADE_CIR_ARR'] + cw['TEMPO_CIR_MESES'] / 12.0
cw['DELTA_IDADE'] = cw['IDADE_ALC'] - cw['IDADE_ESTIMADA']
print(f'\n=== IDADE ===')
print(f'  N com idade comparável: {cw["DELTA_IDADE"].notna().sum()}')
print(f'  DELTA (idade_alc - idade_estimada): mediana={cw["DELTA_IDADE"].median():.1f}, p25={cw["DELTA_IDADE"].quantile(0.25):.1f}, p75={cw["DELTA_IDADE"].quantile(0.75):.1f}')
print(f'  Discordância > 2 anos: {(cw["DELTA_IDADE"].abs()>2).sum()}')
print(f'  Discordância > 5 anos: {(cw["DELTA_IDADE"].abs()>5).sum()}')

# === IMC_pre planilha vs IMC_PRE Arruda ===
cw['IMC_PRE_ALC'] = pd.to_numeric(cw['IMC_pre'], errors='coerce')
cw['IMC_PRE_ARR'] = pd.to_numeric(cw['IMC_PRE'], errors='coerce')
both_imc = cw[cw['IMC_PRE_ALC'].notna() & cw['IMC_PRE_ARR'].notna()]
both_imc_delta = (both_imc['IMC_PRE_ALC'] - both_imc['IMC_PRE_ARR']).abs()
print(f'\n=== IMC PRÉ ===')
print(f'  N com IMC pré em ambas: {len(both_imc)}')
print(f'  Delta absoluto: mediana={both_imc_delta.median():.2f}, p75={both_imc_delta.quantile(0.75):.2f}')
print(f'  Discordância > 1 kg/m²: {(both_imc_delta>1).sum()}')
print(f'  Discordância > 3 kg/m²: {(both_imc_delta>3).sum()}')

# === Tempo cirurgia ===
# Se temos data atual aproximada (vamos usar 2024-06-01 como referência da coleta de dados)
# DATA_CIRURGIA Arruda + Tempo_cir(meses) = ~ data coleta
# Vamos verificar se Tempo_cir_planilha é consistente com agora
cw['DT_CIR_ESTIMADA_PLANILHA'] = cw.apply(
    lambda r: (datetime(2024,6,1) - timedelta(days=int(r['TEMPO_CIR_MESES']*30.44)))
              if pd.notna(r['TEMPO_CIR_MESES']) else None,
    axis=1
)
cw['DELTA_DT_CIR_DIAS'] = cw.apply(
    lambda r: (r['DT_CIR'] - r['DT_CIR_ESTIMADA_PLANILHA']).days
              if r['DT_CIR'] and r['DT_CIR_ESTIMADA_PLANILHA'] else None,
    axis=1
)
print(f'\n=== DATA CIRURGIA ===')
print(f'  N com ambas datas: {cw["DELTA_DT_CIR_DIAS"].notna().sum()}')
print(f'  Delta dias (Arruda - estimada da planilha): mediana={cw["DELTA_DT_CIR_DIAS"].median():.0f}')
print(f'  Discordância > 6 meses: {(cw["DELTA_DT_CIR_DIAS"].abs()>180).sum()}')
print(f'  Discordância > 1 ano: {(cw["DELTA_DT_CIR_DIAS"].abs()>365).sum()}')

# === Salvar flags ===
flags = cw[['planilha_row','NOME_ALC','PACIENTEID','NOME_ARRUDA_FULL','tier','score',
            'SEXO_ALC','SEXO_ARR','IDADE_ALC','IDADE_ESTIMADA','DELTA_IDADE',
            'IMC_PRE_ALC','IMC_PRE_ARR','TEMPO_CIR_MESES','DT_CIR']].copy()
flags['FLAG_SEXO'] = flags.apply(lambda r: r['SEXO_ALC']!=r['SEXO_ARR'] and pd.notna(r['SEXO_ALC']) and pd.notna(r['SEXO_ARR']), axis=1)
flags['FLAG_IDADE'] = flags['DELTA_IDADE'].abs() > 5
flags['FLAG_IMC'] = (flags['IMC_PRE_ALC'] - flags['IMC_PRE_ARR']).abs() > 3

flags['ANY_FLAG'] = flags['FLAG_SEXO'] | flags['FLAG_IDADE'] | flags['FLAG_IMC']
print(f'\n=== TOTAL FLAGS ===')
print(f'  Pacientes com qualquer flag: {flags["ANY_FLAG"].sum()}/{len(flags)}')

flags.to_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/AUDITORIA_FLAGS.csv', index=False)

# Relatório
report = f"""# Auditoria de Consistência — Estudo Álcool x Arruda

**N linkados:** {len(cw)}

## Sexo
- Concordantes: {sexo_match.sum()}/{len(cw)}
- Discordantes: {len(sexo_disc)}

## Idade
- Comparáveis: {cw["DELTA_IDADE"].notna().sum()}
- Delta mediano: {cw["DELTA_IDADE"].median():.1f} anos
- Discordância >5 anos: {(cw["DELTA_IDADE"].abs()>5).sum()}

## IMC pré-cirurgia
- Comparáveis: {len(both_imc)}
- Delta absoluto mediano: {both_imc_delta.median():.2f} kg/m²
- Discordância >3 kg/m²: {(both_imc_delta>3).sum()}

## Tempo cirurgia
- Comparáveis: {cw["DELTA_DT_CIR_DIAS"].notna().sum()}
- Delta mediano: {cw["DELTA_DT_CIR_DIAS"].median():.0f} dias
- Discordância >1 ano: {(cw["DELTA_DT_CIR_DIAS"].abs()>365).sum()}

## Resumo
**Pacientes com QUALQUER flag de inconsistência grave:** {flags["ANY_FLAG"].sum()}/{len(flags)}
"""
with open('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/resultados/02_auditoria_consistencia.md',
          'w', encoding='utf-8') as f:
    f.write(report)
print('\nRelatório salvo.')
