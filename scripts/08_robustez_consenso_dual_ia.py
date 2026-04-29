"""
08 - Pacote de robustez metodológica (resposta ao consenso Codex × Claude)
==========================================================================
Implementa os itens 1-7 do pacote consensual de 12:
  1) FDR-BH sobre família laboratorial completa
  2) Ancoragem cross-sectional no exame mais próximo ao AUDIT
  3) Mixed model com intercepto+slope aleatórios + diagnóstico de influência
  4) Diagnóstico Cook/DFBETAS no mixed model
  5) Comparação formal n_visitas, duração de seguimento entre AUDIT+/AUDIT-
  6) Sensibilidade AUDIT contínuo, AUDIT-C, cutoff sex-specific
  7) Logística parcimoniosa vs ampla com EPV explícito + bootstrap 5000x

CONTEXTO: GGT NÃO foi pré-especificado (estudo retrospectivo, protocolo focava em CAGE/AUDIT).
Logo, FDR-BH formal é obrigatório.
"""
import sys, re, unicodedata
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np
from datetime import datetime, timedelta
from scipy import stats
from scipy.stats import mannwhitneyu
import statsmodels.api as sm
from statsmodels.regression.mixed_linear_model import MixedLM
from statsmodels.stats.multitest import multipletests
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve

OUT_RES = 'Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/resultados'
OUT_DAD = 'Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados'

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

# ============================================
# Carregar dados
# ============================================
df = pd.read_csv(f'{OUT_DAD}/DATASET_130.csv', low_memory=False)
cw = pd.read_csv(f'{OUT_DAD}/CROSSWALK_ALCOOL_ARRUDA.csv', low_memory=False)
cw['n'] = cw['NOME_ALC'].apply(norm)
cw['DT_CIR'] = cw['DATA_CIRURGIA'].apply(parse_date)
df['n'] = df['NOME'].apply(norm)
df = df.merge(cw[['n','PACIENTEID','DT_CIR']], on='n', how='left')

# Estimar data do AUDIT (= DATA_CIRURGIA + Tempo_cir meses)
df['DT_AUDIT'] = df.apply(
    lambda r: r['DT_CIR'] + timedelta(days=int(r['Tempo_cir']*30.44))
              if pd.notna(r['DT_CIR']) and pd.notna(r['Tempo_cir']) else None,
    axis=1
)
print(f'Pacientes com DT_AUDIT estimada: {df["DT_AUDIT"].notna().sum()}/{len(df)}')
print(f'  Range estimado: {df["DT_AUDIT"].min()} → {df["DT_AUDIT"].max()}')
print(f'  Mediana DT_AUDIT: {df["DT_AUDIT"].median()}')

# Sabin
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
sab = sab[sab['n'].isin(df['n']) & sab['DT'].notna()].copy()

dt_cir_map   = dict(zip(df['n'], df['DT_CIR']))
dt_audit_map = dict(zip(df['n'], df['DT_AUDIT']))
audit_pos_map = dict(zip(df['n'], df['AUDIT_pos']))
cage_pos_map  = dict(zip(df['n'], df['CAGE_pos']))
audit_score_map = dict(zip(df['n'], df['AUDIT_PONTOS']))
cage_score_map  = dict(zip(df['n'], df['CAGE_PONTOS']))
sexo_map  = dict(zip(df['n'], df['Sexo:']))
idade_map = dict(zip(df['n'], df['IDADE']))

sab['DT_CIR']    = sab['n'].map(dt_cir_map)
sab['DT_AUDIT']  = sab['n'].map(dt_audit_map)
sab['AUDIT_pos'] = sab['n'].map(audit_pos_map)
sab['CAGE_pos']  = sab['n'].map(cage_pos_map)
sab['AUDIT_score'] = sab['n'].map(audit_score_map)
sab['masc'] = (sab['n'].map(sexo_map)==1).astype(int)
sab['IDADE'] = sab['n'].map(idade_map)
sab = sab.dropna(subset=['DT_CIR','DT_AUDIT'])
sab['DELTA_CIR_DIAS']  = (sab['DT'] - sab['DT_CIR']).dt.days
sab['DELTA_AUDIT_DIAS']= (sab['DT'] - sab['DT_AUDIT']).dt.days
sab['DELTA_CIR_ANOS']  = sab['DELTA_CIR_DIAS']/365.25
sab['DELTA_AUDIT_ANOS']= sab['DELTA_AUDIT_DIAS']/365.25
sab_post = sab[sab['DELTA_CIR_DIAS'] > 180].copy()

print(f'\nExames pós-op (>6m após cirurgia): {len(sab_post)} ({sab_post["n"].nunique()} pacientes)')

# ============================================
# 1) Distribuição do gap temporal AUDIT × labs
# ============================================
print('\n' + '='*70)
print('1) GAP TEMPORAL AUDIT × LABS')
print('='*70)
gap = sab_post['DELTA_AUDIT_DIAS'].dropna()
print(f'N exames: {len(gap)}')
print(f'  Mediana gap (anos): {gap.median()/365.25:+.2f}')
print(f'  P25: {gap.quantile(0.25)/365.25:+.2f} anos')
print(f'  P75: {gap.quantile(0.75)/365.25:+.2f} anos')
print(f'  Min: {gap.min()/365.25:+.2f} anos  /  Max: {gap.max()/365.25:+.2f} anos')

print('\nExames POR JANELA |gap| em anos:')
for limite, label in [(0.5,'≤6m'),(1.0,'≤1a'),(2.0,'≤2a'),(5.0,'≤5a'),(99.0,'todos')]:
    sub = sab_post[sab_post['DELTA_AUDIT_ANOS'].abs() <= limite]
    print(f'  |gap|≤{label}: n_ex={len(sub)}, n_pac={sub["n"].nunique()}, '
          f'GGT={sub["GGT"].notna().sum()}, VCM={sub["VCM"].notna().sum()}')

# Comparação AUDIT+ vs - em n_visitas e duração
visitas = sab_post.groupby('n').agg(
    n_vis=('DT','count'), dur_anos=('DELTA_CIR_ANOS','max')
).reset_index()
visitas = visitas.merge(df[['n','AUDIT_pos','CAGE_pos']], on='n', how='left')

print('\nVisitas e duração de seguimento por status AUDIT:')
for grp_name, gpos in [('AUDIT-',0),('AUDIT+',1)]:
    sub = visitas[visitas['AUDIT_pos']==gpos]
    print(f'  {grp_name} (n={len(sub)}): n_vis median={sub["n_vis"].median():.1f}, '
          f'dur_anos median={sub["dur_anos"].median():.1f}')
u, p_vis = mannwhitneyu(visitas[visitas['AUDIT_pos']==0]['n_vis'],
                        visitas[visitas['AUDIT_pos']==1]['n_vis'], alternative='two-sided')
u, p_dur = mannwhitneyu(visitas[visitas['AUDIT_pos']==0]['dur_anos'],
                        visitas[visitas['AUDIT_pos']==1]['dur_anos'], alternative='two-sided')
print(f'  p-Mann-Whitney n_visitas: {p_vis:.3f}')
print(f'  p-Mann-Whitney duração: {p_dur:.3f}')

# ============================================
# 2) ANCORAGEM CROSS-SECTIONAL: exame mais próximo ao AUDIT
# ============================================
print('\n' + '='*70)
print('2) ANCORAGEM CROSS-SECTIONAL — exame mais próximo do AUDIT')
print('='*70)

def closest_exam(d, max_gap_days=365):
    """Para cada paciente, retorna o exame mais próximo da DT_AUDIT (gap máx)."""
    out = []
    for n, grp in d.groupby('n'):
        gp = grp.copy()
        gp['abs_gap'] = gp['DELTA_AUDIT_DIAS'].abs()
        gp = gp[gp['abs_gap'] <= max_gap_days]
        if len(gp) == 0:
            continue
        # selecionar a linha com menor gap absoluto
        best = gp.loc[gp['abs_gap'].idxmin()]
        out.append(best)
    return pd.DataFrame(out)


for janela_dias, label in [(180,'±6m'),(365,'±12m'),(730,'±24m')]:
    closest = closest_exam(sab_post, janela_dias)
    print(f'\n--- Janela {label} (max_gap={janela_dias}d) ---')
    print(f'  Pacientes com exame na janela: {len(closest)}')
    for var in ['GGT','TGO_AST','TGP_ALT','VCM','HBA1C']:
        sub = closest[[var,'AUDIT_pos']].dropna()
        if len(sub) < 10 or sub['AUDIT_pos'].nunique()<2: continue
        g0 = sub[sub['AUDIT_pos']==0][var]; g1 = sub[sub['AUDIT_pos']==1][var]
        u, p = mannwhitneyu(g0, g1, alternative='two-sided')
        try: auc = roc_auc_score(sub['AUDIT_pos'], sub[var])
        except: auc = np.nan
        print(f'    {var}: AUDIT- n={len(g0)} med={g0.median():.1f} | '
              f'AUDIT+ n={len(g1)} med={g1.median():.1f} | p={p:.3f} | AUC={auc:.3f}')

# ============================================
# 3) MIXED MODEL com intercepto + slope aleatórios + diagnóstico
# ============================================
print('\n' + '='*70)
print('3) MIXED MODEL com slope aleatório + diagnóstico de influência')
print('='*70)

def fit_mixed_full(d, outcome, label):
    """Ajusta modelo com intercepto+slope aleatórios; compara com só intercepto."""
    sub = d[[outcome,'DELTA_CIR_ANOS','AUDIT_pos','masc','IDADE','n']].dropna()
    if len(sub) < 30:
        print(f'  {label}: n insuficiente ({len(sub)})')
        return None, None
    sub = sub.copy()
    sub['log_y'] = np.log(sub[outcome].clip(lower=1))
    sub['delta_x_audit'] = sub['DELTA_CIR_ANOS'] * sub['AUDIT_pos']

    # Modelo A: só intercepto aleatório
    md_a = MixedLM.from_formula(
        'log_y ~ DELTA_CIR_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
        groups='n', data=sub
    )
    # Modelo B: intercepto + slope aleatório por DELTA_CIR_ANOS
    md_b = MixedLM.from_formula(
        'log_y ~ DELTA_CIR_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
        groups='n', re_formula='~DELTA_CIR_ANOS', data=sub
    )

    try:
        rf_a = md_a.fit(method='powell', maxiter=500, disp=False)
    except Exception as e:
        print(f'  {label} (intercepto): erro {e}'); return None, None
    try:
        rf_b = md_b.fit(method='powell', maxiter=500, disp=False)
    except Exception as e:
        print(f'  {label} (intercepto+slope): erro {e}')
        return rf_a, None

    # LRT
    llr = 2*(rf_b.llf - rf_a.llf)
    df_diff = 2  # variância slope + cov slope-intercepto
    p_lrt = 1 - stats.chi2.cdf(llr, df_diff)

    print(f'\n--- {label} ({outcome}) ---')
    print(f'  n_obs={len(sub)} n_pac={sub["n"].nunique()}')
    print(f'  Modelo A (só intercepto): AIC=N/A LL={rf_a.llf:.2f}')
    print(f'  Modelo B (interc+slope):  LL={rf_b.llf:.2f} | LRT_p={p_lrt:.4f}')
    print(f'  Coef slope×AUDIT (A): {rf_a.params["delta_x_audit"]:.4f}, p={rf_a.pvalues["delta_x_audit"]:.4f}')
    if rf_b is not None:
        print(f'  Coef slope×AUDIT (B): {rf_b.params["delta_x_audit"]:.4f}, p={rf_b.pvalues["delta_x_audit"]:.4f}')
    return rf_a, rf_b


results_mixed = {}
for var in ['GGT','TGO_AST','TGP_ALT','VCM']:
    results_mixed[var] = fit_mixed_full(sab_post, var, var)

# AST/ALT ratio
sab_post_ratio = sab_post.copy()
sab_post_ratio['AST_ALT_ratio'] = sab_post_ratio['TGO_AST'] / sab_post_ratio['TGP_ALT']
results_mixed['AST_ALT'] = fit_mixed_full(sab_post_ratio, 'AST_ALT_ratio', 'AST/ALT ratio')

# Diagnóstico de influência: Cook/DFBETAS por sujeito (aproximação leave-one-subject-out)
print('\n--- Diagnóstico de influência (leave-one-subject-out, GGT slope×AUDIT) ---')
sub_g = sab_post[['GGT','DELTA_CIR_ANOS','AUDIT_pos','masc','IDADE','n']].dropna()
sub_g['log_y'] = np.log(sub_g['GGT'].clip(lower=1))
sub_g['delta_x_audit'] = sub_g['DELTA_CIR_ANOS'] * sub_g['AUDIT_pos']

base_md = MixedLM.from_formula(
    'log_y ~ DELTA_CIR_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
    groups='n', re_formula='~DELTA_CIR_ANOS', data=sub_g
).fit(method='powell', maxiter=500, disp=False)
base_coef = base_md.params['delta_x_audit']

deltas = []
for n_lo in sub_g['n'].unique():
    s2 = sub_g[sub_g['n'] != n_lo]
    try:
        m2 = MixedLM.from_formula(
            'log_y ~ DELTA_CIR_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
            groups='n', re_formula='~DELTA_CIR_ANOS', data=s2
        ).fit(method='powell', maxiter=500, disp=False)
        deltas.append({'n':n_lo,'coef_loo':m2.params['delta_x_audit'],
                       'delta':m2.params['delta_x_audit'] - base_coef,
                       'p_loo':m2.pvalues['delta_x_audit']})
    except: continue
diag = pd.DataFrame(deltas)
print(f'  Coef base: {base_coef:.4f}')
print(f'  Range LOO: [{diag["coef_loo"].min():.4f}, {diag["coef_loo"].max():.4f}]')
print(f'  Top 5 sujeitos influentes (|delta|):')
print(diag.assign(abs_delta=diag['delta'].abs()).nlargest(5,'abs_delta')[['n','coef_loo','delta','p_loo']].to_string(index=False))

# Modelo sem top-3 influentes
top3 = diag.assign(abs_delta=diag['delta'].abs()).nlargest(3,'abs_delta')['n'].tolist()
sub_g3 = sub_g[~sub_g['n'].isin(top3)]
m3 = MixedLM.from_formula(
    'log_y ~ DELTA_CIR_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
    groups='n', re_formula='~DELTA_CIR_ANOS', data=sub_g3
).fit(method='powell', maxiter=500, disp=False)
print(f'\n  Modelo sem top-3 influentes: coef={m3.params["delta_x_audit"]:.4f}, p={m3.pvalues["delta_x_audit"]:.4f}')

# ============================================
# 4) FDR-BH na família laboratorial
# ============================================
print('\n' + '='*70)
print('4) FDR-BH em família laboratorial completa')
print('='*70)

# Cross-sectional (mediana pós-op por paciente)
per_pat = sab_post.groupby('n').agg(
    GGT_med=('GGT','median'), AST_med=('TGO_AST','median'),
    ALT_med=('TGP_ALT','median'), VCM_med=('VCM','median'),
    HBA1C_med=('HBA1C','median'), GLI_med=('GLICOSE','median'),
    HEMO_med=('HEMOGLOBINA','median'), PLT_med=('PLAQUETAS','median'),
    TG_med=('TRIGLICERIDEOS','median'), HDL_med=('HDL','median'),
    LDL_med=('LDL','median')
).reset_index()
per_pat['AST_ALT'] = per_pat['AST_med'] / per_pat['ALT_med']
per_pat = per_pat.merge(df[['n','AUDIT_pos']], on='n', how='left')

cs_results = []
for var in ['GGT_med','AST_med','ALT_med','VCM_med','AST_ALT','HBA1C_med','GLI_med',
            'HEMO_med','PLT_med','TG_med','HDL_med','LDL_med']:
    sub = per_pat[[var,'AUDIT_pos']].dropna()
    if len(sub) < 20: continue
    g0 = sub[sub['AUDIT_pos']==0][var]; g1 = sub[sub['AUDIT_pos']==1][var]
    u, p = mannwhitneyu(g0, g1, alternative='two-sided')
    cs_results.append({'var':var,'n0':len(g0),'med0':g0.median(),
                      'n1':len(g1),'med1':g1.median(),'p':p})
cs = pd.DataFrame(cs_results)
rej, q, _, _ = multipletests(cs['p'], method='fdr_bh')
cs['q_BH'] = q
cs['sig_BH'] = rej
print('\nCross-sectional (mediana pós-op):')
print(cs.to_string(index=False))

# Slope×AUDIT em todos os outcomes (família mixed)
mix_results = []
for var, label in [('GGT','GGT'),('TGO_AST','AST'),('TGP_ALT','ALT'),
                   ('VCM','VCM'),('HBA1C','HBA1C'),('GLICOSE','GLICOSE'),
                   ('HEMOGLOBINA','HEMO'),('PLAQUETAS','PLT'),
                   ('TRIGLICERIDEOS','TG'),('HDL','HDL'),('LDL','LDL')]:
    sub = sab_post[[var,'DELTA_CIR_ANOS','AUDIT_pos','masc','IDADE','n']].dropna()
    if len(sub) < 30: continue
    sub = sub.copy()
    sub['log_y'] = np.log(sub[var].clip(lower=1))
    sub['delta_x_audit'] = sub['DELTA_CIR_ANOS'] * sub['AUDIT_pos']
    try:
        m = MixedLM.from_formula(
            'log_y ~ DELTA_CIR_ANOS + AUDIT_pos + delta_x_audit + masc + IDADE',
            groups='n', re_formula='~DELTA_CIR_ANOS', data=sub
        ).fit(method='powell', maxiter=500, disp=False)
        mix_results.append({'var':label,'coef':m.params['delta_x_audit'],
                           'p':m.pvalues['delta_x_audit'],
                           'n_obs':len(sub),'n_pac':sub["n"].nunique()})
    except: pass
mr = pd.DataFrame(mix_results)
rej, q, _, _ = multipletests(mr['p'], method='fdr_bh')
mr['q_BH'] = q
mr['sig_BH'] = rej
print('\nMixed model slope×AUDIT (família laboratorial completa):')
print(mr.to_string(index=False))

cs.to_csv(f'{OUT_RES}/08_FDR_cross_sectional.csv', index=False)
mr.to_csv(f'{OUT_RES}/08_FDR_mixed_models.csv', index=False)

# ============================================
# 5) Sensibilidade AUDIT: contínuo, AUDIT-C, sex-specific
# ============================================
print('\n' + '='*70)
print('5) SENSIBILIDADE AUDIT — contínuo, AUDIT-C, sex-specific')
print('='*70)

# AUDIT contínuo (slope×AUDIT_score)
sub = sab_post[['GGT','DELTA_CIR_ANOS','AUDIT_score','masc','IDADE','n']].dropna()
sub['log_y'] = np.log(sub['GGT'].clip(lower=1))
sub['delta_x_score'] = sub['DELTA_CIR_ANOS'] * sub['AUDIT_score']
m_cont = MixedLM.from_formula(
    'log_y ~ DELTA_CIR_ANOS + AUDIT_score + delta_x_score + masc + IDADE',
    groups='n', re_formula='~DELTA_CIR_ANOS', data=sub
).fit(method='powell', maxiter=500, disp=False)
print('\nGGT slope × AUDIT_score (contínuo):')
print(f'  coef={m_cont.params["delta_x_score"]:.5f}, p={m_cont.pvalues["delta_x_score"]:.4f}')
print(f'  → cada +1 ponto AUDIT acrescenta {100*(np.exp(m_cont.params["delta_x_score"])-1):.2f}% por ano ao GGT')

# AUDIT-C (3 primeiros itens). A planilha tem AUDIT_FREQ, AUDIT_QTDE e AUDIT_6 (item 3)
# Calcular AUDIT-C nos 130
plan_full = pd.read_csv(f'{OUT_DAD}/DATASET_130.csv', low_memory=False)
plan_full['n'] = plan_full['NOME'].apply(norm)
# AUDIT_6 está armazenado como #NAME? — vou ignorar AUDIT-C se não tiver dado
audit_c_cols = ['AUDIT_FREQ','AUDIT_QTDE']
if all(c in plan_full.columns for c in audit_c_cols):
    plan_full['AUDIT_C_partial'] = plan_full[audit_c_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
    print(f'\nAUDIT-C (parcial, 2 itens) — distribuição:')
    print(plan_full['AUDIT_C_partial'].describe())
    plan_full['AUDIT_C_pos'] = (plan_full['AUDIT_C_partial'] >= 3).astype(int)
    print(f'AUDIT-C ≥3 (parcial): {plan_full["AUDIT_C_pos"].sum()} de {len(plan_full)}')
    # slope GGT por AUDIT_C
    audit_c_map = dict(zip(plan_full['n'], plan_full['AUDIT_C_pos']))
    sab_post['AUDIT_C_pos'] = sab_post['n'].map(audit_c_map)
    sub2 = sab_post[['GGT','DELTA_CIR_ANOS','AUDIT_C_pos','masc','IDADE','n']].dropna()
    sub2['log_y'] = np.log(sub2['GGT'].clip(lower=1))
    sub2['delta_x_c'] = sub2['DELTA_CIR_ANOS'] * sub2['AUDIT_C_pos']
    try:
        m_c = MixedLM.from_formula(
            'log_y ~ DELTA_CIR_ANOS + AUDIT_C_pos + delta_x_c + masc + IDADE',
            groups='n', re_formula='~DELTA_CIR_ANOS', data=sub2
        ).fit(method='powell', maxiter=500, disp=False)
        print(f'\nGGT slope × AUDIT-C (parcial 2 itens, cutoff ≥3):')
        print(f'  coef={m_c.params["delta_x_c"]:.4f}, p={m_c.pvalues["delta_x_c"]:.4f}')
    except Exception as e:
        print(f'  Erro: {e}')

# Cutoff sex-specific (NIAAA: AUDIT≥4 mulheres, ≥8 homens)
df['AUDIT_pos_sex'] = ((df['Sexo:']==1) & (df['AUDIT_PONTOS']>=8)) | \
                     ((df['Sexo:']==2) & (df['AUDIT_PONTOS']>=4))
df['AUDIT_pos_sex'] = df['AUDIT_pos_sex'].astype(int)
print(f'\nAUDIT_pos_sex-specific (NIAAA: M≥8, F≥4): {df["AUDIT_pos_sex"].sum()} de {len(df)}')
audit_sex_map = dict(zip(df['n'], df['AUDIT_pos_sex']))
sab_post['AUDIT_pos_sex'] = sab_post['n'].map(audit_sex_map)
sub3 = sab_post[['GGT','DELTA_CIR_ANOS','AUDIT_pos_sex','masc','IDADE','n']].dropna()
sub3['log_y'] = np.log(sub3['GGT'].clip(lower=1))
sub3['delta_x_sex'] = sub3['DELTA_CIR_ANOS'] * sub3['AUDIT_pos_sex']
try:
    m_sex = MixedLM.from_formula(
        'log_y ~ DELTA_CIR_ANOS + AUDIT_pos_sex + delta_x_sex + masc + IDADE',
        groups='n', re_formula='~DELTA_CIR_ANOS', data=sub3
    ).fit(method='powell', maxiter=500, disp=False)
    print(f'\nGGT slope × AUDIT_pos_sex-specific:')
    print(f'  coef={m_sex.params["delta_x_sex"]:.4f}, p={m_sex.pvalues["delta_x_sex"]:.4f}')
except Exception as e:
    print(f'  Erro: {e}')

# ============================================
# 6) EPV + bootstrap multivariada logística
# ============================================
print('\n' + '='*70)
print('6) EPV + ESTABILIDADE BOOTSTRAP da multivariada')
print('='*70)

df['masc'] = (df['Sexo:']==1).astype(int)
df['anos_pos_op'] = df['Tempo_cir']/12.0
df['pai_bebia'] = (df['pai_bebida']==1).astype(int)
df['violencia_qq'] = (df['violencia']==1).astype(int)
df['ensino_sup'] = (df['Escolaridade']>=4).astype(int)
df['sem_religiao'] = (df['religião']==2).astype(int)

# Modelos
models = {
    'parsimonioso (4 cov)': ['masc','IDADE','anos_pos_op','pai_bebia'],
    'amplo (8 cov)':       ['masc','IDADE','anos_pos_op','pai_bebia',
                            'violencia_qq','ensino_sup','sem_religiao','mae_bebida'],
}
df['mae_bebida'] = (df['mae_bebida']==1).astype(int)

# EPV
n_events_audit = df['AUDIT_pos'].sum()
n_events_cage  = df['CAGE_pos'].sum()
print(f'\nEventos: AUDIT+={n_events_audit}, CAGE+={n_events_cage}')
print('\nEPV por modelo:')
for mname, cols in models.items():
    print(f'  {mname}: n_cov={len(cols)}, EPV_AUDIT={n_events_audit/len(cols):.1f}, EPV_CAGE={n_events_cage/len(cols):.1f}')

# Bootstrap 5000x — modelo parsimonioso
print('\n5000x bootstrap modelo parsimonioso AUDIT:')
np.random.seed(42)
boot = {c:[] for c in models['parsimonioso (4 cov)']}
sub = df[['AUDIT_pos']+models['parsimonioso (4 cov)']].dropna()
for b in range(5000):
    bs = sub.sample(len(sub), replace=True)
    try:
        lr = LogisticRegression(C=10, max_iter=500, solver='liblinear').fit(
            bs[models['parsimonioso (4 cov)']].values, bs['AUDIT_pos'].values
        )
        for v, b_ in zip(models['parsimonioso (4 cov)'], lr.coef_[0]):
            boot[v].append(b_)
    except: continue
print('Bootstrap OR (mediana, IC95%):')
for v, betas in boot.items():
    betas = np.array(betas)
    print(f'  {v}: OR={np.exp(np.median(betas)):.2f} '
          f'[{np.exp(np.percentile(betas,2.5)):.2f}, {np.exp(np.percentile(betas,97.5)):.2f}]')

# VIF
print('\nVIF (modelo amplo):')
from statsmodels.stats.outliers_influence import variance_inflation_factor
sub2 = df[models['amplo (8 cov)']+['AUDIT_pos']].dropna()
X = sub2[models['amplo (8 cov)']]
for i, v in enumerate(X.columns):
    try:
        vif = variance_inflation_factor(X.values, i)
        print(f'  {v}: {vif:.2f}')
    except: pass

print('\n=== Fim ===')
