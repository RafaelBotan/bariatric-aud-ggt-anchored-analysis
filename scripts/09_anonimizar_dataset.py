"""
09 - Anonimização do dataset 130 para depósito público (OSF/GitHub)
====================================================================
Cria DATASET_130_ANON.csv removendo:
  - Nome (substituído por ID sequencial P001-P130)
  - Datas absolutas (mantém apenas Tempo_cir em meses, fora de risco re-identificação)
  - Quaisquer chaves diretas (PACIENTEID, NOMEs originais, datas de cirurgia)

Mantém:
  - Variáveis psicométricas (CAGE, AUDIT individuais e totais)
  - Variáveis demográficas (sexo, idade, escolaridade, religião, etnia, renda, filhos)
  - Comportamentos (pai bebia, mãe bebia, bebida atual/anterior, tipo)
  - Violência, prejuízos
  - Antropometria (IMC pré, mín, atual)
  - Tempo desde cirurgia (meses)

Para o painel laboratorial (necessário para reproduzir Fig 1, Fig 2, Tab 3),
exporta painel agregado por paciente (ID anônimo) com gap em dias relativo
ao AUDIT (mas NÃO a data absoluta).

CEP/CAAE: 34717119.4.0000.5553
"""
import sys, re, unicodedata
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np
from datetime import datetime, timedelta

OUT_SUB = 'Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/submission_OBES_SURG/dados_anon'

def norm(s):
    if pd.isna(s) or s is None: return ''
    s = str(s).lower().strip(); s = re.sub(r'#l\b','',s)
    s = unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii')
    s = re.sub(r'[^a-z\s]',' ',s); s = re.sub(r'\s+',' ',s).strip()
    return s

def parse_date(x):
    if pd.isna(x): return None
    s = str(x).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d','%d/%m/%Y','%d/%m/%y'):
        try: return datetime.strptime(s,fmt)
        except: pass
    return None

# === Carregar dataset 130 + crosswalk ===
df = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/DATASET_130.csv',
                 low_memory=False)
df['n'] = df['NOME'].apply(norm)
cw = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/CROSSWALK_ALCOOL_ARRUDA.csv',
                 low_memory=False)
cw['n'] = cw['NOME_ALC'].apply(norm)
cw['DT_CIR'] = cw['DATA_CIRURGIA'].apply(parse_date)
df = df.merge(cw[['n','PACIENTEID','DT_CIR']], on='n', how='left')

# Estimar DT_AUDIT
df['DT_AUDIT'] = df.apply(
    lambda r: r['DT_CIR'] + timedelta(days=int(r['Tempo_cir']*30.44))
              if pd.notna(r['DT_CIR']) and pd.notna(r['Tempo_cir']) else None, axis=1)

# === Atribuir ID anônimo sequencial ===
df_sorted = df.sort_values(['NOME']).reset_index(drop=True)
df_sorted['STUDY_ID'] = ['P' + str(i+1).zfill(3) for i in range(len(df_sorted))]

# === Crosswalk INTERNO (NÃO publicado, fica só local para auditoria) ===
crosswalk_interno = df_sorted[['STUDY_ID','NOME','PACIENTEID']].copy()
crosswalk_interno.to_csv(
    'Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/CROSSWALK_INTERNO_NAO_PUBLICAR.csv',
    index=False)
print(f'Crosswalk interno (NÃO PUBLICAR): {len(crosswalk_interno)} pacientes')

# === Dataset anonimizado ===
keep_cols = [
    'STUDY_ID',
    'Tempo_cir','IMC_pre','IMC_Min','IMC_atual','IDADE',
    'Sexo:','Estado Civil','Escolaridade','religião','ETNIA','RENDA','filhos',
    'violencia','pai_bebida','mae_bebida','Bebida atua','Bebida ant','tipo',
    'preju amiza','preju famili','preju finan','preju trab',
    'CAGE_ABORRECIDO','CAGE_CULPADO','CAGE_MANHA','CAGE_PARAR','CAGE_PONTOS',
    'AUDIT_FREQ','AUDIT_QTDE','AUDIT_NAOPARAR','AUDIT_TAREFA','AUDIT_MANHA',
    'AUDIT_CULPA','AUDIT_NOITE','AUDIT_FERIDO','AUDIT_PREOCUP','AUDIT_PONTOS',
    'CAGE_pos','AUDIT_pos',
    'DM2','HAS','DISLIPIDEMIA','ESTEATOSE','DEPRESSAO','DRC_PREVIA','N_COMORBIDADES',
]
keep_cols = [c for c in keep_cols if c in df_sorted.columns]
anon = df_sorted[keep_cols].copy()
# rename portugues → ascii padrão
rename = {
    'Sexo:': 'sex', 'Estado Civil': 'marital_status', 'Escolaridade': 'education',
    'religião': 'religion', 'ETNIA': 'ethnicity', 'RENDA': 'income', 'filhos': 'children',
    'violencia': 'violence_any', 'pai_bebida': 'father_drank', 'mae_bebida': 'mother_drank',
    'Bebida atua': 'current_drinking', 'Bebida ant': 'past_drinking', 'tipo': 'beverage_type',
    'preju amiza': 'harm_friendship', 'preju famili': 'harm_family',
    'preju finan': 'harm_financial', 'preju trab': 'harm_work',
    'IDADE': 'age_years', 'Tempo_cir': 'time_since_surgery_months',
    'IMC_pre': 'BMI_preop', 'IMC_Min': 'BMI_min', 'IMC_atual': 'BMI_current',
    'CAGE_PONTOS': 'CAGE_score', 'AUDIT_PONTOS': 'AUDIT_score',
    'CAGE_pos': 'CAGE_pos', 'AUDIT_pos': 'AUDIT_pos',
    'DM2': 'T2DM_preop', 'HAS': 'HTN_preop', 'DISLIPIDEMIA': 'dyslipidemia_preop',
    'ESTEATOSE': 'NAFLD_preop', 'DEPRESSAO': 'depression_preop',
    'DRC_PREVIA': 'CKD_preop', 'N_COMORBIDADES': 'n_comorbidities_preop',
}
anon = anon.rename(columns=rename)
anon.to_csv(f'{OUT_SUB}/DATASET_130_ANON.csv', index=False)
print(f'Dataset anonimizado: {anon.shape} → {OUT_SUB}/DATASET_130_ANON.csv')

# === Painel laboratorial anonimizado (long format) ===
sab = pd.read_csv('Y:/Estudos_Arruda_Galvao/01_BASES_FINAIS/sabin_laboratorial/MEGA_BASE_ARRUDA.csv',
                  usecols=['NOME','DATA_ATENDIMENTO','GGT','TGO_AST','TGP_ALT','VCM','HBA1C',
                           'GLICOSE','HEMOGLOBINA','PLAQUETAS','TRIGLICERIDEOS','HDL','LDL',
                           'COLESTEROL_TOTAL','ALBUMINA','BILIRRUBINA_TOTAL'],
                  low_memory=False)
LAB = ['GGT','TGO_AST','TGP_ALT','VCM','HBA1C','GLICOSE','HEMOGLOBINA','PLAQUETAS',
       'TRIGLICERIDEOS','HDL','LDL','COLESTEROL_TOTAL','ALBUMINA','BILIRRUBINA_TOTAL']
for c in LAB:
    sab[c] = pd.to_numeric(sab[c], errors='coerce')
sab['n'] = sab['NOME'].apply(norm)
sab['DT'] = sab['DATA_ATENDIMENTO'].apply(parse_date)
nome_to_id = dict(zip(df_sorted['n'], df_sorted['STUDY_ID']))
nome_to_audit = dict(zip(df_sorted['n'], df_sorted['DT_AUDIT']))
nome_to_cir = dict(zip(df_sorted['n'], df_sorted['DT_CIR']))

sab_link = sab[sab['n'].isin(df_sorted['n']) & sab['DT'].notna()].copy()
sab_link['STUDY_ID'] = sab_link['n'].map(nome_to_id)
sab_link['DT_AUDIT'] = sab_link['n'].map(nome_to_audit)
sab_link['DT_CIR']   = sab_link['n'].map(nome_to_cir)
sab_link['gap_audit_days'] = (sab_link['DT'] - sab_link['DT_AUDIT']).dt.days
sab_link['gap_surgery_days'] = (sab_link['DT'] - sab_link['DT_CIR']).dt.days

# Renomear LAB columns
LAB_RENAME = {'TGO_AST':'AST','TGP_ALT':'ALT','HBA1C':'HBA1C','GLICOSE':'glucose',
              'HEMOGLOBINA':'hemoglobin','PLAQUETAS':'platelets',
              'TRIGLICERIDEOS':'triglycerides','HDL':'HDL','LDL':'LDL',
              'COLESTEROL_TOTAL':'total_cholesterol','ALBUMINA':'albumin',
              'BILIRRUBINA_TOTAL':'total_bilirubin'}
sab_link = sab_link.rename(columns=LAB_RENAME)
out_cols = ['STUDY_ID','gap_audit_days','gap_surgery_days'] + \
           ['GGT','AST','ALT','VCM','HBA1C','glucose','hemoglobin','platelets',
            'triglycerides','HDL','LDL','total_cholesterol','albumin','total_bilirubin']
sab_anon = sab_link[out_cols].copy()
sab_anon.to_csv(f'{OUT_SUB}/LAB_PANEL_LONG_ANON.csv', index=False)
print(f'Painel laboratorial: {sab_anon.shape} → {OUT_SUB}/LAB_PANEL_LONG_ANON.csv')

# === README do depósito ===
readme = """# Estudo Álcool Arruda — Datasets Anonimizados

**CEP/CAAE:** 34717119.4.0000.5553
**Data de geração:** 2026-04-28

## Conteúdo

### `DATASET_130_ANON.csv`
Dataset principal — N=130 pacientes pós-bariátricos com CAGE/AUDIT.
- Identificador: `STUDY_ID` (P001-P130, sequencial sem relação com data ou ordem clínica)
- Variáveis psicométricas, demográficas, antropométricas, padrão de consumo, prejuízos
- Comorbidades pré-cirurgia (binárias)
- **Sem nomes, sem datas absolutas, sem identificadores institucionais**

### `LAB_PANEL_LONG_ANON.csv`
Painel laboratorial Sabin em formato long — uma linha por exame.
- Vinculável ao dataset principal via `STUDY_ID`
- Tempo: `gap_audit_days` (dias relativos ao questionário AUDIT, negativo = antes), `gap_surgery_days` (dias relativos à cirurgia)
- **Sem datas absolutas**

## Reprodução das análises

Scripts em [GitHub repo](https://github.com/<usuario>/bariatric-aud-ggt-analysis):
- `01_linkage_e_consolidacao.py` — não aplicável (já anonimizado)
- `02_auditoria_consistencia.py` — não aplicável
- `03_replicar_descritivo_e_multivariada.py` — adaptar para usar STUDY_ID
- `04_biomarcadores_sabin.py` — usar `LAB_PANEL_LONG_ANON.csv`
- `08_robustez_consenso_dual_ia.py` — análises principais reproduzíveis aqui

## Licença e uso

Dados depositados sob restrição de uso ético — qualquer reanálise requer:
1. Solicitação formal aos autores
2. Aprovação CEP da instituição requisitante
3. Citação ao manuscrito original (DOI a inserir após publicação)

Scripts: licença MIT.

## Citação

[Citação do manuscrito a preencher após publicação]
"""
with open(f'{OUT_SUB}/README.md', 'w', encoding='utf-8') as f:
    f.write(readme)
print(f'\nREADME criado: {OUT_SUB}/README.md')
print('\n✓ Anonimização concluída.')
