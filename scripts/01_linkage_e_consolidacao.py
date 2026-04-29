"""
01 - Linkagem robusta e consolidação de bases
=============================================
Objetivo: levar a linkagem dos 138 pacientes do estudo de álcool com:
  - ARRUDA_SUPER_BASE_v2.csv (clínica/antropométrica)
  - MEGA_BASE_ARRUDA.csv (Sabin, exames longitudinais)
  - MEGA_BASE_LABORATORIAIS.csv (consolidado pré/3M/6M/12M)
  - BASE_PARA_IA_v2.csv (texto narrativo)

Estratégia:
  Tier 1: match exato sobre nome normalizado (lower, sem acento, sem #L)
  Tier 2: fuzzy match (rapidfuzz) sobre não-linkados, threshold 88%
  Tier 3: relatório dos não-linkados após fuzzy para revisão manual

Saída:
  trabalho/dados/CROSSWALK_ALCOOL_ARRUDA.csv
  trabalho/resultados/01_linkage_report.md
"""
import sys, os, re, unicodedata
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, openpyxl
from rapidfuzz import process, fuzz

ROOT_ALC = 'Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda'
ROOT_ARR = 'Y:/Estudos_Arruda_Galvao/01_BASES_FINAIS/arruda'
ROOT_SAB = 'Y:/Estudos_Arruda_Galvao/01_BASES_FINAIS/sabin_laboratorial'
ROOT_LAB = 'Y:/Estudos_Arruda_Galvao/ARCHIVED/SergioArruda_IMC_vs_IRC'
ROOT_IA  = 'Y:/Estudos_Arruda_Galvao/03_DADOS_BRUTOS_AUDITORIA/arruda_prontuario'

OUT_DADOS = os.path.join(ROOT_ALC, 'trabalho/dados')
OUT_RES   = os.path.join(ROOT_ALC, 'trabalho/resultados')
os.makedirs(OUT_DADOS, exist_ok=True)
os.makedirs(OUT_RES, exist_ok=True)


def norm(s):
    if pd.isna(s) or s is None: return ''
    s = str(s).lower().strip()
    s = re.sub(r'#l\b', '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-z\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# === Carrega planilha de álcool ===
print('Carregando planilha de álcool...')
wb = openpyxl.load_workbook(os.path.join(ROOT_ALC, 'Planilha - 140 pacientes (1) (8).xlsx'),
                            data_only=True)
ws = wb['Planilha1']

alc_rows = []
HDR = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
COLS = {h: i for i, h in enumerate(HDR) if h}
for r in range(2, ws.max_row + 1):
    nome = ws.cell(r, 1).value
    if not nome or not str(nome).strip():
        continue
    row = {'planilha_row': r, 'NOME_RAW': str(nome).strip()}
    for h, idx in COLS.items():
        v = ws.cell(r, idx + 1).value
        row[h] = v
    alc_rows.append(row)

alc = pd.DataFrame(alc_rows)
alc['n'] = alc['NOME_RAW'].apply(norm)
print(f'  Pacientes na planilha: {len(alc)} (norm únicos: {alc["n"].nunique()})')

# === Arruda Super Base ===
print('Carregando ARRUDA_SUPER_BASE_v2...')
arr = pd.read_csv(os.path.join(ROOT_ARR, 'ARRUDA_SUPER_BASE_v2.csv'),
                  usecols=['PACIENTEID', 'NOME', 'SEXO', 'DATANASCIMENTO',
                           'DATA_CIRURGIA', 'IDADE_CIRURGIA', 'IMC_PRE'],
                  low_memory=False)
arr['n'] = arr['NOME'].apply(norm)
print(f'  Pacientes Arruda: {len(arr)} (norm únicos: {arr["n"].nunique()})')

# === Tier 1: match exato ===
arr_dict = arr.set_index('n', drop=False)
match_t1 = []
miss_t1 = []
for _, row in alc.iterrows():
    if row['n'] in arr_dict.index:
        h = arr_dict.loc[row['n']]
        if isinstance(h, pd.DataFrame):
            h = h.iloc[0]
        match_t1.append({
            'planilha_row': row['planilha_row'],
            'NOME_ALC': row['NOME_RAW'],
            'PACIENTEID': h['PACIENTEID'],
            'NOME_ARR': h['NOME'],
            'tier': 'T1_exato',
            'score': 100,
        })
    else:
        miss_t1.append(row)

print(f'\nTier 1 (match exato): {len(match_t1)}/{len(alc)}')
print(f'  Não-linkados restantes: {len(miss_t1)}')

# === Tier 2: fuzzy ===
# Estratégia em duas passadas:
#   2a) token_set_ratio threshold 90 — robusto a sobrenomes adicionais
#       (ex.: short name vs full name with extra surname → token_set 100)
#   2b) token_sort_ratio threshold 88 — fallback para variações de ordem
# Em todos os matches, exigir que primeiro+último token batam OU >=2 tokens
# em comum, para evitar "Maria Aparecida X" colando com "Maria Aparecida Y"
print('\nTier 2 (fuzzy rapidfuzz)...')
arr_names = arr['n'].tolist()


def tokens_ok(a, b):
    ta = a.split()
    tb = b.split()
    if not ta or not tb:
        return False
    if ta[0] != tb[0]:
        return False
    common = set(ta) & set(tb)
    return len(common) >= 2 or (len(ta) <= 2 and ta[-1] in tb) or (len(tb) <= 2 and tb[-1] in ta)


match_t2 = []
miss_t2 = []
for row in miss_t1:
    # 2a: token_set
    cand_set = process.extract(row['n'], arr_names, scorer=fuzz.token_set_ratio,
                               limit=3)
    # 2b: token_sort
    cand_sort = process.extract(row['n'], arr_names, scorer=fuzz.token_sort_ratio,
                                limit=3)

    best_match = None
    if cand_set[0][1] >= 90 and tokens_ok(row['n'], cand_set[0][0]):
        best_match = ('T2a_set', cand_set[0])
    elif cand_sort[0][1] >= 88 and tokens_ok(row['n'], cand_sort[0][0]):
        best_match = ('T2b_sort', cand_sort[0])

    if best_match:
        tier_name, (best_n, best_s, _) = best_match
        h = arr_dict.loc[best_n]
        if isinstance(h, pd.DataFrame):
            h = h.iloc[0]
        match_t2.append({
            'planilha_row': row['planilha_row'],
            'NOME_ALC': row['NOME_RAW'],
            'PACIENTEID': h['PACIENTEID'],
            'NOME_ARR': h['NOME'],
            'tier': tier_name,
            'score': best_s,
        })
    else:
        miss_t2.append({
            'planilha_row': row['planilha_row'],
            'NOME_ALC': row['NOME_RAW'],
            'NOME_ALC_NORM': row['n'],
            'cand1_set': cand_set[0][0], 'score1_set': cand_set[0][1],
            'cand1_sort': cand_sort[0][0], 'score1_sort': cand_sort[0][1],
            'cand2_set': cand_set[1][0] if len(cand_set) > 1 else '',
            'score2_set': cand_set[1][1] if len(cand_set) > 1 else 0,
        })

print(f'  Match Tier 2 (≥88%): {len(match_t2)}')
print(f'  Não-linkados após Tier 2: {len(miss_t2)}')

# === Tier 3: resgate manual ===
# Manual rescue for residual cases where the abbreviated middle initial
# matches an unambiguous full middle name in the master cohort and the
# token_sort score remained ≥80 with first+last name identical.
# (Names redacted for de-identification in the public release.)
manual_rescue = {
    # Format: 'questionnaire spreadsheet entry': 'master cohort entry'
    # (1 entry rescued in this study; redacted in public release)
}
manual_rescued = []
for row in list(miss_t2):
    if row['NOME_ALC'] in manual_rescue:
        target_n = manual_rescue[row['NOME_ALC']]
        if target_n in arr_dict.index:
            h = arr_dict.loc[target_n]
            if isinstance(h, pd.DataFrame):
                h = h.iloc[0]
            match_t2.append({
                'planilha_row': row['planilha_row'],
                'NOME_ALC': row['NOME_ALC'],
                'PACIENTEID': h['PACIENTEID'],
                'NOME_ARR': h['NOME'],
                'tier': 'T3_manual',
                'score': 100,
            })
            manual_rescued.append(row['NOME_ALC'])

miss_t2 = [r for r in miss_t2 if r['NOME_ALC'] not in manual_rescue]
print(f'  Tier 3 (resgate manual): +{len(manual_rescued)}')
print(f'  Não-linkados final: {len(miss_t2)}')

# === Crosswalk final ===
crosswalk = pd.DataFrame(match_t1 + match_t2)
crosswalk = crosswalk.merge(
    arr[['n', 'PACIENTEID', 'NOME', 'SEXO', 'DATANASCIMENTO',
         'DATA_CIRURGIA', 'IDADE_CIRURGIA', 'IMC_PRE']]
        .rename(columns={'NOME': 'NOME_ARRUDA_FULL'}),
    left_on='PACIENTEID', right_on='PACIENTEID', how='left'
)

# Merge planilha completa (todas as colunas)
crosswalk = crosswalk.merge(
    alc, left_on='planilha_row', right_on='planilha_row', how='left',
    suffixes=('', '_ALC')
)

crosswalk.to_csv(os.path.join(OUT_DADOS, 'CROSSWALK_ALCOOL_ARRUDA.csv'), index=False)
print(f'\nCrosswalk salvo: {len(crosswalk)} pacientes linkados')

# Não-linkados para revisão manual
miss_df = pd.DataFrame(miss_t2)
miss_df.to_csv(os.path.join(OUT_DADOS, 'NAO_LINKADOS_PARA_REVISAO.csv'), index=False)

# Relatório
report = f"""# Linkage Report — Estudo Álcool x Arruda Super Base

**Pacientes na planilha:** {len(alc)}
**Linkagem Tier 1 (exato):** {len(match_t1)}/{len(alc)} ({100*len(match_t1)/len(alc):.1f}%)
**Linkagem Tier 2 (fuzzy ≥88%):** {len(match_t2)} adicionais
**Total linkados:** {len(crosswalk)}/{len(alc)} ({100*len(crosswalk)/len(alc):.1f}%)
**Não linkados (após fuzzy):** {len(miss_t2)}

## Não-linkados — candidatos para revisão manual

| Nome planilha | Top candidato | Score |
|---|---|---|
"""
for _, r in miss_df.iterrows():
    report += f"| {r['NOME_ALC']} | {r.get('cand1_set','')} (set={r.get('score1_set',0):.0f}, sort={r.get('score1_sort',0):.0f}) |\n"

with open(os.path.join(OUT_RES, '01_linkage_report.md'), 'w', encoding='utf-8') as f:
    f.write(report)

print('\nRelatório salvo em trabalho/resultados/01_linkage_report.md')
