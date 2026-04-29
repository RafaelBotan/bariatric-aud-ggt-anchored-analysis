"""
07 - Análises de sensibilidade + coorte Arruda completa
========================================================
A) Trajetória GGT excluindo esteatose pré e DM2 (confundidores hepáticos)
B) Paradoxo HbA1c (AUDIT+ menor): confundido por DM2 status?
C) Coorte completa Arruda (n=1.869): aplicar TXT_SCORE para estimar prevalência
D) Validar pelo lab: GGT/VCM elevados na coorte Arruda completa por TXT_SCORE
E) Análise por janela temporal (estratificada): pico bioquímico
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np, re, unicodedata
from datetime import datetime
import statsmodels.api as sm
from statsmodels.regression.mixed_linear_model import MixedLM
from sklearn.metrics import roc_auc_score

def norm(s):
    if pd.isna(s) or s is None: return ''
    s = str(s).lower().strip()
    s = re.sub(r'#l\b','',s)
    s = unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii')
    s = re.sub(r'[^a-z\s]',' ',s); s = re.sub(r'\s+',' ',s).strip()
    return s

def parse_date(x):
    if pd.isna(x): return None
    s = str(x).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d','%d/%m/%Y','%d/%m/%y'):
        try: return datetime.strptime(s, fmt)
        except: pass
    return None

# === Carregar dados ===
df130 = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/DATASET_130.csv', low_memory=False)
df130['n'] = df130['NOME'].apply(norm)
cw = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/CROSSWALK_ALCOOL_ARRUDA.csv', low_memory=False)
cw['n'] = cw['NOME_ALC'].apply(norm)

# Arruda completa com comorbidades
arr = pd.read_csv('Y:/Estudos_Arruda_Galvao/01_BASES_FINAIS/arruda/ARRUDA_SUPER_BASE_v2.csv',
                  usecols=['PACIENTEID','NOME','SEXO','DATA_CIRURGIA','IDADE_CIRURGIA',
                           'IMC_PRE','DM2','HAS','DISLIPIDEMIA','ESTEATOSE','DEPRESSAO','DRC_PREVIA',
                           'N_COMORBIDADES'],
                  low_memory=False)
arr['n'] = arr['NOME'].apply(norm)
arr['DT_CIR'] = arr['DATA_CIRURGIA'].apply(parse_date)
print(f'Arruda total: {len(arr)}')

# Merge comorbidades nos 130
df130 = df130.merge(arr[['n','DM2','HAS','DISLIPIDEMIA','ESTEATOSE','DEPRESSAO','DRC_PREVIA','N_COMORBIDADES','DT_CIR']],
                   on='n', how='left')

# === A) Trajetória GGT excluindo esteatose ===
print('\n=== ANÁLISE DE SENSIBILIDADE: trajetória GGT/VCM ===')
sab = pd.read_csv('Y:/Estudos_Arruda_Galvao/01_BASES_FINAIS/sabin_laboratorial/MEGA_BASE_ARRUDA.csv',
                  usecols=['NOME','DATA_ATENDIMENTO','GGT','TGO_AST','TGP_ALT','VCM','HBA1C'],
                  low_memory=False)
for c in ['GGT','TGO_AST','TGP_ALT','VCM','HBA1C']:
    sab[c] = pd.to_numeric(sab[c], errors='coerce')
sab['n'] = sab['NOME'].apply(norm)
sab['DT'] = sab['DATA_ATENDIMENTO'].apply(parse_date)

# Marca exames pós-op nos 130
nome_to_dtcir = dict(zip(df130['n'], df130['DT_CIR']))
sab['DT_CIR'] = sab['n'].map(nome_to_dtcir)
sab130 = sab[sab['n'].isin(df130['n']) & sab['DT'].notna() & sab['DT_CIR'].notna()].copy()
sab130['DELTA_ANOS'] = (sab130['DT'] - sab130['DT_CIR']).dt.days / 365.25
post130 = sab130[sab130['DELTA_ANOS'] > 0.5].merge(
    df130[['n','AUDIT_pos','CAGE_pos','Sexo:','IDADE','ESTEATOSE','DM2','DISLIPIDEMIA','HAS','DEPRESSAO','DRC_PREVIA']], on='n', how='left'
)
post130['masc'] = (post130['Sexo:']==1).astype(int)


def fit_mix(d, outcome, label):
    sub = d[[outcome,'DELTA_ANOS','AUDIT_pos','masc','IDADE','n']].dropna()
    if len(sub) < 30:
        print(f'  {label}: n={len(sub)} insuficiente, pulado')
        return None
    sub = sub.copy()
    sub['log_y'] = np.log(sub[outcome].clip(lower=1))
    sub['delta_x_audit'] = sub['DELTA_ANOS'] * sub['AUDIT_pos']
    try:
        md = MixedLM.from_formula('log_y ~ DELTA_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
                                  groups='n', data=sub)
        mr = md.fit(method='powell', maxiter=300, disp=False)
        coef = mr.params['delta_x_audit']
        p = mr.pvalues['delta_x_audit']
        print(f'  {label} ({outcome}): n_obs={len(sub)} n_pac={sub["n"].nunique()} | '
              f'slope_x_AUDIT coef={coef:.4f} p={p:.4f}')
        return mr
    except Exception as e:
        print(f'  {label}: erro {type(e).__name__}: {str(e)[:60]}')
        return None


# Codificar comorbidades binárias
for c in ['ESTEATOSE','DM2','DISLIPIDEMIA','HAS','DEPRESSAO','DRC_PREVIA']:
    if c in post130.columns:
        post130[c+'_bin'] = (post130[c]=='SIM').astype(int)
    else:
        print(f'  AVISO: coluna {c} ausente, usando 0')
        post130[c+'_bin'] = 0

print('\nDistribuição comorbidades nos 130 (coorte do estudo):')
for c in ['ESTEATOSE','DM2','DISLIPIDEMIA','HAS','DEPRESSAO']:
    pcs = post130[['n',c+'_bin']].drop_duplicates()
    print(f'  {c}: SIM em {pcs[c+"_bin"].sum()}/{len(pcs)} pacientes')

print('\nTrajetória completa (referência):')
fit_mix(post130, 'GGT', 'GGT total')
fit_mix(post130, 'VCM', 'VCM total')


def fit_mix_extra(d, outcome, label, extra_covars):
    sub = d[[outcome,'DELTA_ANOS','AUDIT_pos','masc','IDADE','n'] + extra_covars].dropna()
    if len(sub) < 30:
        print(f'  {label}: n={len(sub)} insuficiente')
        return None
    sub = sub.copy()
    sub['log_y'] = np.log(sub[outcome].clip(lower=1))
    sub['delta_x_audit'] = sub['DELTA_ANOS'] * sub['AUDIT_pos']
    formula = 'log_y ~ DELTA_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE + ' + ' + '.join(extra_covars)
    try:
        md = MixedLM.from_formula(formula, groups='n', data=sub)
        mr = md.fit(method='powell', maxiter=300, disp=False)
        coef = mr.params['delta_x_audit']
        p = mr.pvalues['delta_x_audit']
        print(f'  {label}: n_obs={len(sub)} | slope_x_AUDIT coef={coef:.4f} p={p:.4f}')
        return mr
    except Exception as e:
        print(f'  {label}: erro {type(e).__name__}: {str(e)[:60]}')
        return None


print('\nAjustado por ESTEATOSE_bin:')
fit_mix_extra(post130, 'GGT', 'GGT + esteatose', ['ESTEATOSE_bin'])

print('Ajustado por DM2_bin:')
fit_mix_extra(post130, 'GGT', 'GGT + DM2', ['DM2_bin'])

print('Ajustado por DISLIPIDEMIA_bin:')
fit_mix_extra(post130, 'GGT', 'GGT + dislip', ['DISLIPIDEMIA_bin'])

print('Ajustado por TODAS comorbidades (esteatose+DM2+dislip+HAS):')
fit_mix_extra(post130, 'GGT', 'GGT + todas', ['ESTEATOSE_bin','DM2_bin','DISLIPIDEMIA_bin','HAS_bin'])

print('\nExcluindo esteatose=SIM (subamostra):')
sub_no_est = post130[post130['ESTEATOSE_bin'] == 0]
print(f'  n_pac sem esteatose: {sub_no_est["n"].nunique()}')
fit_mix(sub_no_est, 'GGT', 'GGT s/ esteatose')

print('\nExcluindo DM2=SIM:')
sub_no_dm = post130[post130['DM2_bin'] == 0]
print(f'  n_pac sem DM2: {sub_no_dm["n"].nunique()}')
fit_mix(sub_no_dm, 'GGT', 'GGT s/ DM2')

print('\nApenas masculinos:')
fit_mix(post130[post130['masc']==1].copy(), 'GGT', 'GGT só masc')

print('\nApenas femininas:')
fit_mix(post130[post130['masc']==0].copy(), 'GGT', 'GGT só fem')

# === B) Paradoxo HbA1c ===
print('\n=== Paradoxo HbA1c — confundido por DM2? ===')
bio = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/BIOQUIMICA_PERPATIENT.csv',
                  low_memory=False)
m = df130.merge(bio[['n','HBA1C_med','GGT_med']], on='n', how='left')

print('\nHbA1c por AUDIT+ e DM2:')
grp = m[m['HBA1C_med'].notna()].groupby(['AUDIT_pos','DM2'])['HBA1C_med'].agg(['count','median']).reset_index()
print(grp.to_string())

print('\nHbA1c por AUDIT+ exclui DM2:')
sub = m[(m['DM2']=='NAO') & m['HBA1C_med'].notna()]
g0 = sub[sub['AUDIT_pos']==0]['HBA1C_med']; g1 = sub[sub['AUDIT_pos']==1]['HBA1C_med']
from scipy.stats import mannwhitneyu
u, p = mannwhitneyu(g0, g1, alternative='two-sided') if len(g0)>1 and len(g1)>1 else (np.nan, np.nan)
print(f'  AUDIT- (n={len(g0)}): med={g0.median():.2f}')
print(f'  AUDIT+ (n={len(g1)}): med={g1.median():.2f}')
print(f'  p={p:.3f}')

# === C/D) Coorte completa Arruda — TXT_SCORE para inferir prevalência ===
print('\n=== COORTE COMPLETA: aplicar TXT_SCORE em N=1869 ===')
txt = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/TEXTO_IA_SCORE.csv', low_memory=False)
arr_t = arr.merge(txt[['PACIENTEID','TXT_SCORE']], on='PACIENTEID', how='left')
print(f'Arruda com TXT_SCORE: {arr_t["TXT_SCORE"].notna().sum()}/{len(arr_t)}')

print('\nDistribuição TXT_SCORE na coorte Arruda completa:')
print(arr_t['TXT_SCORE'].value_counts().sort_index())

# Estimativa de prevalência usando o cutoff calibrado nos 130 (TXT≥2)
# Se TXT_SCORE >= 2 prediz AUDIT+ com Sens=0.81, Esp=0.56 (validação interna),
# podemos aplicar como rastreio na coorte completa.
# Cuidado: PPV=0.38 → maioria dos TXT≥2 são FALSOS POSITIVOS.
# Mais útil: prevalência APARENTE vs estimativa corrigida (ajustada por sens/esp)
# Prevalência observada > sens × prev_real + (1-esp) × (1-prev_real)
# Resolvendo para prev_real:
sens = 0.81; esp = 0.56
prev_obs_2 = (arr_t['TXT_SCORE']>=2).mean()
prev_real_2 = (prev_obs_2 - (1-esp)) / (sens - (1-esp))
print(f'\nPrevalência aparente TXT≥2: {prev_obs_2:.1%}')
print(f'Prevalência real estimada (correção sens/esp): {max(0,prev_real_2):.1%}')

sens3 = 0.33; esp3 = 0.89
prev_obs_3 = (arr_t['TXT_SCORE']>=3).mean()
prev_real_3 = (prev_obs_3 - (1-esp3)) / (sens3 - (1-esp3))
print(f'Prevalência aparente TXT≥3: {prev_obs_3:.1%}')
print(f'Prevalência real estimada (correção sens/esp): {max(0,prev_real_3):.1%}')

# Cross-check com nossos 130: prev observada AUDIT+ = 24.6%
print(f'Prev. AUDIT+ documentada nos 130: 24.6%')

# Validação biológica na coorte completa: GGT mediano por TXT_SCORE
arr_full_n = set(arr['n'])
sab_arr = sab[sab['n'].isin(arr_full_n) & sab['DT'].notna() & sab['DT_CIR'].notna()].copy()
sab_arr['DT_CIR'] = sab_arr['n'].map(dict(zip(arr['n'], arr['DT_CIR'])))
sab_arr['DELTA_ANOS'] = (sab_arr['DT'] - sab_arr['DT_CIR']).dt.days / 365.25
sab_post = sab_arr[sab_arr['DELTA_ANOS'] > 0.5]
gpat = sab_post.groupby('n').agg(GGT_med=('GGT','median'), VCM_med=('VCM','median'),
                                  AST_med=('TGO_AST','median'), ALT_med=('TGP_ALT','median')).reset_index()
arr_t = arr_t.merge(gpat, on='n', how='left')

print('\n=== Validação biológica: GGT/VCM por TXT_SCORE em coorte completa Arruda ===')
print(arr_t.groupby('TXT_SCORE')[['GGT_med','VCM_med','AST_med','ALT_med']].agg(['count','median']).to_string())

# Dose-resposta TXT_SCORE → GGT
sub = arr_t.dropna(subset=['TXT_SCORE','GGT_med'])
print(f'\nN com TXT_SCORE+GGT na coorte completa: {len(sub)}')
print('Spearman TXT_SCORE x GGT_med:', sub[['TXT_SCORE','GGT_med']].corr(method='spearman').iloc[0,1])
# Mann-Whitney TXT_SCORE>=2 vs <2
g0 = sub[sub['TXT_SCORE']<2]['GGT_med']; g1 = sub[sub['TXT_SCORE']>=2]['GGT_med']
u, p = mannwhitneyu(g0, g1, alternative='two-sided')
print(f'GGT TXT<2 (n={len(g0)}, med={g0.median():.1f}) vs TXT>=2 (n={len(g1)}, med={g1.median():.1f})  p={p:.4g}')

arr_t.to_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/COORTE_COMPLETA_ARRUDA_COM_SCORE.csv', index=False)
print('Salvo coorte completa.')
