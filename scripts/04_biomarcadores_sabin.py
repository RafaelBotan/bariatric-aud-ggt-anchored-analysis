"""
04 - Análise de biomarcadores hepatobioquímicos (Sabin) por status de álcool
============================================================================
Hipótese: pacientes com AUDIT+ ou CAGE+ apresentam GGT, AST, ALT, VCM
elevados em relação aos negativos no follow-up pós-cirurgia.

Análises:
  A) Cross-sectional: valor mediano por paciente (todos os exames pós-op)
       em AUDIT+ vs AUDIT-, ajustado para sexo, idade, tempo cirurgia
  B) Trajetória: modelo misto de GGT/VCM/AST vs tempo desde cirurgia,
       interação com AUDIT+ (slope test)
  C) Curva ROC: AUC do GGT (mediana pós-op) e VCM para predizer AUDIT+
       Calcular cutoff ótimo (Youden) e PPV/NPV
  D) Z-score laboratorial individualizado:
       Para cada paciente AUDIT+, calcular GGT z-score contra coorte
       Arruda completa pareada por sexo+idade+tempo cirurgia (matching 1:5)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np, re, unicodedata
from datetime import datetime
import statsmodels.api as sm
from statsmodels.regression.mixed_linear_model import MixedLM
from sklearn.metrics import roc_auc_score, roc_curve

def norm(s):
    if pd.isna(s) or s is None: return ''
    s = str(s).lower().strip()
    s = re.sub(r'#l\b', '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-z\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def parse_date(x):
    if pd.isna(x): return None
    s = str(x).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d','%d/%m/%Y','%d/%m/%y','%Y-%m-%dT%H:%M:%S'):
        try: return datetime.strptime(s, fmt)
        except: pass
    return None


# === Carregar dataset 130 ===
df130 = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/DATASET_130.csv',
                   low_memory=False)
cw = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/CROSSWALK_ALCOOL_ARRUDA.csv',
                 low_memory=False)
print(f'130 dataset: {len(df130)}')

# Crosswalk: NOME -> PACIENTEID + dt_cir
cw['n'] = cw['NOME_ALC'].apply(norm)
cw['DT_CIR'] = cw['DATA_CIRURGIA'].apply(parse_date)
df130['n'] = df130['NOME'].apply(norm)
df130 = df130.merge(cw[['n','PACIENTEID','DT_CIR']], on='n', how='left')

# === Sabin labs ===
sab = pd.read_csv('Y:/Estudos_Arruda_Galvao/01_BASES_FINAIS/sabin_laboratorial/MEGA_BASE_ARRUDA.csv',
                  usecols=['NOME','DATA_ATENDIMENTO','GGT','TGO_AST','TGP_ALT','VCM',
                           'HEMOGLOBINA','HEMATOCRITO','PLAQUETAS','GLICOSE','HBA1C',
                           'COLESTEROL_TOTAL','HDL','LDL','TRIGLICERIDEOS','CREATININA',
                           'TFG_ESTIMADA','BILIRRUBINA_TOTAL','ALBUMINA'],
                  low_memory=False)
sab['n'] = sab['NOME'].apply(norm)
sab['DT'] = sab['DATA_ATENDIMENTO'].apply(parse_date)

# Forçar todos os labs a numérico (alguns podem ter '<5' ou '>100')
LAB_COLS = ['GGT','TGO_AST','TGP_ALT','VCM','HEMOGLOBINA','HEMATOCRITO','PLAQUETAS',
            'GLICOSE','HBA1C','COLESTEROL_TOTAL','HDL','LDL','TRIGLICERIDEOS',
            'CREATININA','TFG_ESTIMADA','BILIRRUBINA_TOTAL','ALBUMINA']
for c in LAB_COLS:
    sab[c] = pd.to_numeric(sab[c], errors='coerce')

# Filtrar para os 130
sab130 = sab[sab['n'].isin(df130['n'])].copy()
nome_to_dtcir = dict(zip(df130['n'], df130['DT_CIR']))
sab130['DT_CIR'] = sab130['n'].map(nome_to_dtcir)
sab130 = sab130.dropna(subset=['DT', 'DT_CIR'])
sab130['DELTA_DIAS'] = (sab130['DT'] - sab130['DT_CIR']).dt.days
sab130['DELTA_ANOS'] = sab130['DELTA_DIAS']/365.25
print(f'Exames Sabin nos 130: {len(sab130)} ({sab130["n"].nunique()} pacientes)')

# === A) Cross-sectional: valor mediano POSTOP (>180 dias) por paciente ===
post = sab130[sab130['DELTA_DIAS'] > 180].copy()
print(f'\nExames pós-op (>180d): {len(post)} ({post["n"].nunique()} pacientes)')

per_pat = post.groupby('n').agg(
    GGT_med=('GGT','median'), GGT_max=('GGT','max'),
    AST_med=('TGO_AST','median'), AST_max=('TGO_AST','max'),
    ALT_med=('TGP_ALT','median'), ALT_max=('TGP_ALT','max'),
    VCM_med=('VCM','median'), VCM_max=('VCM','max'),
    TG_med=('TRIGLICERIDEOS','median'),
    HBA1C_med=('HBA1C','median'),
    HDL_med=('HDL','median'),
    LDL_med=('LDL','median'),
    PLT_med=('PLAQUETAS','median'),
    n_visitas=('DT','count'),
    delta_ult=('DELTA_DIAS','max'),
).reset_index()

per_pat['AST_ALT_ratio'] = per_pat['AST_med'] / per_pat['ALT_med']

m = df130[['n','PACIENTEID','Sexo:','IDADE','Tempo_cir','IMC_atual',
           'CAGE_PONTOS','AUDIT_PONTOS','CAGE_pos','AUDIT_pos']].merge(
    per_pat, on='n', how='left'
)
m['masc'] = (m['Sexo:'] == 1).astype(int)

n_lab = m['GGT_med'].notna().sum()
print(f'Pacientes com GGT pós-op: {n_lab}')
print(f'Pacientes com VCM pós-op: {m["VCM_med"].notna().sum()}')
print(f'Pacientes com ≥2 visitas pós-op: {(m["n_visitas"]>=2).sum()}')

# Comparação AUDIT+ vs AUDIT-
def desc_compare(d, var, group='AUDIT_pos'):
    sub = d[[var, group]].dropna()
    g0 = sub[sub[group]==0][var]; g1 = sub[sub[group]==1][var]
    from scipy.stats import mannwhitneyu
    u, p = mannwhitneyu(g0, g1, alternative='two-sided') if len(g0)>1 and len(g1)>1 else (np.nan, np.nan)
    return {'n0':len(g0),'med0':g0.median(),'n1':len(g1),'med1':g1.median(),'p':p}

print('\n=== Cross-sectional: AUDIT+ vs AUDIT- (mediana pós-op) ===')
for var in ['GGT_med','GGT_max','AST_med','ALT_med','VCM_med','VCM_max','AST_ALT_ratio',
            'TG_med','HBA1C_med','HDL_med','PLT_med']:
    r = desc_compare(m, var, 'AUDIT_pos')
    print(f'  {var}: AUDIT- (n={r["n0"]}) med={r["med0"]:.1f} | AUDIT+ (n={r["n1"]}) med={r["med1"]:.1f}  p={r["p"]:.3f}')

print('\n=== Cross-sectional: CAGE+ vs CAGE- ===')
for var in ['GGT_med','VCM_med','AST_med','ALT_med','AST_ALT_ratio']:
    r = desc_compare(m, var, 'CAGE_pos')
    print(f'  {var}: CAGE- med={r["med0"]:.1f} | CAGE+ med={r["med1"]:.1f}  p={r["p"]:.3f}')

# === Modelo logístico: AUDIT_pos ~ GGT, ajustado por sexo+idade+tempo ===
print('\n=== AUC ROC: GGT, VCM, AST/ALT como preditor de AUDIT+ ===')
for var in ['GGT_med','VCM_med','AST_med','ALT_med','AST_ALT_ratio','GGT_max']:
    sub = m[[var,'AUDIT_pos']].dropna()
    if len(sub) > 20 and sub['AUDIT_pos'].nunique() > 1:
        try:
            auc = roc_auc_score(sub['AUDIT_pos'], sub[var])
        except:
            auc = np.nan
        print(f'  {var}: n={len(sub)}, AUC={auc:.3f}')

# Logística ajustada
print('\n=== Logística AUDIT_pos ~ GGT_med (ajustado sexo+idade+tempo) ===')
sub = m[['AUDIT_pos','GGT_med','masc','IDADE','Tempo_cir']].dropna()
sub['log_GGT'] = np.log(sub['GGT_med'].clip(lower=1))
X = sm.add_constant(sub[['log_GGT','masc','IDADE','Tempo_cir']])
mod = sm.Logit(sub['AUDIT_pos'], X).fit(disp=0)
ci = mod.conf_int()
print(pd.DataFrame({
    'OR': np.exp(mod.params),
    'IC_low': np.exp(ci[0]),
    'IC_high': np.exp(ci[1]),
    'p': mod.pvalues
}).to_string())

# === C) Mixed model: trajetória GGT vs tempo, AUDIT como interação ===
print('\n=== Mixed model: GGT ~ delta_anos * AUDIT_pos + sexo + idade ===')
post['n'] = post.index.map(post['n'])  # já existe
post = post.merge(df130[['n','AUDIT_pos','CAGE_pos','Sexo:','IDADE']], on='n', how='left')
post['masc'] = (post['Sexo:']==1).astype(int)

for outcome in ['GGT','VCM','TGO_AST','TGP_ALT']:
    sub = post[[outcome,'DELTA_ANOS','AUDIT_pos','masc','IDADE','n']].dropna()
    if len(sub) < 30: continue
    sub['log_y'] = np.log(sub[outcome].clip(lower=1))
    sub['delta_x_audit'] = sub['DELTA_ANOS'] * sub['AUDIT_pos']
    try:
        md = MixedLM.from_formula(
            f'log_y ~ DELTA_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
            groups='n', data=sub
        )
        mr = md.fit(method='lbfgs', maxiter=200, disp=False)
        print(f'\n--- {outcome} (n_obs={len(sub)}, n_pac={sub["n"].nunique()}) ---')
        out = pd.DataFrame({'coef':mr.params,'se':mr.bse,'p':mr.pvalues})
        print(out.to_string())
    except Exception as e:
        print(f'  {outcome}: erro {e}')

# === Salvar dataset bioquímica ===
m.to_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/BIOQUIMICA_PERPATIENT.csv', index=False)
print('\nDataset bioquímica salvo.')
