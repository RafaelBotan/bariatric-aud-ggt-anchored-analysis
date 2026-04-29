"""
10 - Geração das figuras finais 300 dpi
========================================
Fig 1 — Boxplots GGT em janelas ancoradas ±6m, ±12m, ±24m (3 painéis lado a lado)
Fig 2 — Curvas ROC GGT em 3 janelas
Fig S1 — Trajetórias longitudinais (mixed model, slope aleatório, achado nulo)
Fig S2 — Forest plot multivariada bootstrap (modelo parsimonioso)
"""
import sys, re, unicodedata, os
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl
from sklearn.metrics import roc_curve, roc_auc_score
from scipy.stats import mannwhitneyu

# === Estilo profissional ===
mpl.rcParams['font.family'] = 'DejaVu Sans'
mpl.rcParams['font.size'] = 10
mpl.rcParams['axes.linewidth'] = 0.8
mpl.rcParams['xtick.major.width'] = 0.8
mpl.rcParams['ytick.major.width'] = 0.8
mpl.rcParams['savefig.dpi'] = 300
mpl.rcParams['figure.dpi'] = 100

OUT_FIG = 'Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/submission_OBES_SURG/figures'
os.makedirs(OUT_FIG, exist_ok=True)

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

# === Carrega dados ===
df = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/DATASET_130.csv', low_memory=False)
cw = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/CROSSWALK_ALCOOL_ARRUDA.csv', low_memory=False)
df['n'] = df['NOME'].apply(norm); cw['n'] = cw['NOME_ALC'].apply(norm)
cw['DT_CIR'] = cw['DATA_CIRURGIA'].apply(parse_date)
df = df.merge(cw[['n','PACIENTEID','DT_CIR']], on='n', how='left')
df['DT_AUDIT'] = df.apply(
    lambda r: r['DT_CIR'] + timedelta(days=int(r['Tempo_cir']*30.44))
              if pd.notna(r['DT_CIR']) and pd.notna(r['Tempo_cir']) else None, axis=1)

sab = pd.read_csv('Y:/Estudos_Arruda_Galvao/01_BASES_FINAIS/sabin_laboratorial/MEGA_BASE_ARRUDA.csv',
                  usecols=['NOME','DATA_ATENDIMENTO','GGT','TGO_AST','TGP_ALT','VCM','HBA1C'],
                  low_memory=False)
for c in ['GGT','TGO_AST','TGP_ALT','VCM','HBA1C']:
    sab[c] = pd.to_numeric(sab[c], errors='coerce')
sab['n'] = sab['NOME'].apply(norm); sab['DT'] = sab['DATA_ATENDIMENTO'].apply(parse_date)
sab = sab[sab['n'].isin(df['n']) & sab['DT'].notna()].copy()
m_audit = dict(zip(df['n'], df['DT_AUDIT'])); m_cir = dict(zip(df['n'], df['DT_CIR']))
m_pos = dict(zip(df['n'], df['AUDIT_pos'])); m_sex = dict(zip(df['n'], df['Sexo:']))
m_idade = dict(zip(df['n'], df['IDADE']))
sab['DT_AUDIT'] = sab['n'].map(m_audit); sab['DT_CIR'] = sab['n'].map(m_cir)
sab['AUDIT_pos'] = sab['n'].map(m_pos)
sab = sab.dropna(subset=['DT_CIR','DT_AUDIT'])
sab['DELTA_AUDIT_DIAS'] = (sab['DT'] - sab['DT_AUDIT']).dt.days
sab['DELTA_CIR_DIAS'] = (sab['DT'] - sab['DT_CIR']).dt.days
sab['DELTA_CIR_ANOS'] = sab['DELTA_CIR_DIAS']/365.25
sab_post = sab[sab['DELTA_CIR_DIAS']>180].copy()


# Função: para cada paciente, exame mais próximo do AUDIT (com gap máx)
def closest(d, max_gap_days):
    out = []
    for n, grp in d.groupby('n'):
        gp = grp.copy(); gp['abs_gap'] = gp['DELTA_AUDIT_DIAS'].abs()
        gp = gp[gp['abs_gap'] <= max_gap_days]
        if len(gp)==0: continue
        out.append(gp.loc[gp['abs_gap'].idxmin()])
    return pd.DataFrame(out)


# ========================
# FIG 1 — Boxplots GGT janelas ancoradas
# ========================
print('Gerando Figura 1...')
fig, axes = plt.subplots(1, 3, figsize=(11, 4.2), sharey=True)
janelas = [(180,'±6 months', axes[0]),(365,'±12 months', axes[1]),(730,'±24 months', axes[2])]
COL_NEG = '#4C72B0'  # AUDIT−
COL_POS = '#C44E52'  # AUDIT+
for j_dias, label, ax in janelas:
    closest_df = closest(sab_post, j_dias)
    closest_df = closest_df[closest_df['GGT'].notna()].copy()
    g0 = closest_df[closest_df['AUDIT_pos']==0]['GGT'].values
    g1 = closest_df[closest_df['AUDIT_pos']==1]['GGT'].values
    u, p = mannwhitneyu(g0, g1, alternative='two-sided')
    try: auc = roc_auc_score(closest_df['AUDIT_pos'], closest_df['GGT'])
    except: auc = float('nan')

    bp = ax.boxplot([g0, g1], positions=[0,1], widths=0.55, patch_artist=True,
                    medianprops=dict(color='white', linewidth=1.5),
                    flierprops=dict(marker='o', markersize=3, alpha=0.4),
                    whiskerprops=dict(linewidth=0.8), capprops=dict(linewidth=0.8))
    bp['boxes'][0].set_facecolor(COL_NEG); bp['boxes'][0].set_edgecolor(COL_NEG)
    bp['boxes'][1].set_facecolor(COL_POS); bp['boxes'][1].set_edgecolor(COL_POS)

    # jittered points
    np.random.seed(42)
    ax.scatter(np.random.normal(0,0.06,len(g0)), g0, alpha=0.5, s=11, color=COL_NEG, edgecolors='white', linewidths=0.4, zorder=3)
    ax.scatter(np.random.normal(1,0.06,len(g1)), g1, alpha=0.6, s=11, color=COL_POS, edgecolors='white', linewidths=0.4, zorder=3)

    ax.set_xticks([0,1])
    ax.set_xticklabels([f'AUDIT−\n(n={len(g0)})', f'AUDIT+\n(n={len(g1)})'])
    ax.set_title(f'{label}\nMW p={p:.3f} | AUC={auc:.3f}', fontsize=10, pad=8)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle=':')
    ax.set_ylim(0, 200)

axes[0].set_ylabel('Gamma-glutamyl transferase (U/L)', fontsize=11)
plt.suptitle('Anchored gamma-GT by AUDIT status across temporal windows',
             fontsize=12, fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(f'{OUT_FIG}/Figure1_GGT_anchored_boxplots.png', dpi=300, bbox_inches='tight')
fig.savefig(f'{OUT_FIG}/Figure1_GGT_anchored_boxplots.tiff', dpi=300, bbox_inches='tight', pil_kwargs={'compression':'tiff_lzw'})
plt.close()
print('  ✓ Figure1.png + .tiff')


# ========================
# FIG 2 — ROC curves
# ========================
print('Gerando Figura 2...')
fig, ax = plt.subplots(figsize=(5.5, 5.5))
COLORS = {'180':'#1F77B4','365':'#FF7F0E','730':'#2CA02C'}
LABELS = {'180':'±6 months','365':'±12 months','730':'±24 months'}
for j_dias_str, color in COLORS.items():
    j_dias = int(j_dias_str)
    closest_df = closest(sab_post, j_dias)
    closest_df = closest_df[closest_df['GGT'].notna()].copy()
    if closest_df['AUDIT_pos'].nunique() < 2: continue
    fpr, tpr, _ = roc_curve(closest_df['AUDIT_pos'], closest_df['GGT'])
    auc = roc_auc_score(closest_df['AUDIT_pos'], closest_df['GGT'])
    ax.plot(fpr, tpr, color=color, linewidth=2.0,
            label=f'{LABELS[j_dias_str]} (AUC = {auc:.3f}, n = {len(closest_df)})')

ax.plot([0,1],[0,1], color='gray', linestyle='--', linewidth=0.8, alpha=0.6)
ax.set_xlabel('1 − Specificity', fontsize=11)
ax.set_ylabel('Sensitivity', fontsize=11)
ax.set_title('ROC curves: anchored gamma-GT discriminating AUDIT-positive', fontsize=11, fontweight='bold')
ax.legend(loc='lower right', frameon=True, fontsize=9)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.grid(alpha=0.3, linestyle=':')
ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
plt.tight_layout()
fig.savefig(f'{OUT_FIG}/Figure2_ROC_GGT.png', dpi=300, bbox_inches='tight')
fig.savefig(f'{OUT_FIG}/Figure2_ROC_GGT.tiff', dpi=300, bbox_inches='tight', pil_kwargs={'compression':'tiff_lzw'})
plt.close()
print('  ✓ Figure2.png + .tiff')


# ========================
# FIG S1 — Spaghetti + médias longitudinais (achado nulo)
# ========================
print('Gerando Figura S1...')
fig, ax = plt.subplots(figsize=(8, 5))
post_g = sab_post[sab_post['GGT'].notna() & sab_post['AUDIT_pos'].notna()].copy()
# spaghetti
for n, g in post_g.groupby('n'):
    if len(g) < 2: continue
    g = g.sort_values('DELTA_CIR_ANOS')
    cor = COL_POS if g['AUDIT_pos'].iloc[0]==1 else COL_NEG
    ax.plot(g['DELTA_CIR_ANOS'], g['GGT'], color=cor, alpha=0.18, linewidth=0.6)

# loess médio por grupo (binning anual)
for grp_val, cor, lbl in [(0, COL_NEG, 'AUDIT−'),(1, COL_POS, 'AUDIT+')]:
    sub = post_g[post_g['AUDIT_pos']==grp_val].copy()
    bins = np.arange(0.5, 23, 1)
    sub['bin'] = pd.cut(sub['DELTA_CIR_ANOS'], bins=bins)
    bin_med = sub.groupby('bin', observed=True)['GGT'].median().dropna()
    bin_n = sub.groupby('bin', observed=True)['GGT'].count()
    bin_med = bin_med[bin_n >= 5]  # só bins com n>=5
    if len(bin_med) == 0: continue
    centers = [b.mid for b in bin_med.index]
    ax.plot(centers, bin_med.values, color=cor, linewidth=2.5, marker='o',
            markersize=6, label=lbl)

ax.set_xlabel('Time since bariatric surgery (years)', fontsize=11)
ax.set_ylabel('Gamma-glutamyl transferase (U/L)', fontsize=11)
ax.set_title('Longitudinal gamma-GT trajectories by AUDIT status\n(individual lines + group medians)',
             fontsize=11, fontweight='bold')
ax.legend(loc='upper right', fontsize=10)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.grid(alpha=0.3, linestyle=':')
ax.set_ylim(0, 250)
ax.text(0.02, 0.97, 'Mixed model with random slope:\nslope × AUDIT interaction NS\n(β = 0.016, p = 0.389)',
        transform=ax.transAxes, fontsize=9, va='top',
        bbox=dict(boxstyle='round', facecolor='white', edgecolor='gray', alpha=0.85))
plt.tight_layout()
fig.savefig(f'{OUT_FIG}/FigureS1_GGT_longitudinal_null.png', dpi=300, bbox_inches='tight')
fig.savefig(f'{OUT_FIG}/FigureS1_GGT_longitudinal_null.tiff', dpi=300, bbox_inches='tight', pil_kwargs={'compression':'tiff_lzw'})
plt.close()
print('  ✓ FigureS1.png + .tiff')


# ========================
# FIG S2 — Forest plot multivariada bootstrap
# ========================
print('Gerando Figura S2...')
boot_data = {  # do bootstrap 5000x
    'Male sex':         {'OR': 4.83, 'lo': 1.99, 'hi': 12.83},
    'Paternal drinking':{'OR': 5.17, 'lo': 2.02, 'hi': 14.45},
    'Age (per year)':   {'OR': 0.97, 'lo': 0.93, 'hi': 1.00},
    'Time since surgery (per year)': {'OR': 0.97, 'lo': 0.87, 'hi': 1.08},
}
fig, ax = plt.subplots(figsize=(7.5, 3.5))
y_pos = list(range(len(boot_data)))[::-1]
for (lab, d), y in zip(boot_data.items(), y_pos):
    or_, lo, hi = d['OR'], d['lo'], d['hi']
    sig = (lo > 1) or (hi < 1)
    cor = '#C44E52' if sig else '#888'
    ax.plot([lo, hi], [y, y], color=cor, linewidth=2)
    ax.scatter([or_], [y], s=80, color=cor, zorder=5, edgecolors='white', linewidths=1)

ax.axvline(1, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)
ax.set_yticks(y_pos)
ax.set_yticklabels(list(boot_data.keys()))
ax.set_xscale('log')
ax.set_xlabel('Odds ratio (95% bootstrap CI)', fontsize=11)
ax.set_title('Multivariable predictors of AUDIT≥8 — bootstrap 5000×',
             fontsize=11, fontweight='bold')
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.grid(axis='x', alpha=0.3, linestyle=':')
plt.tight_layout()
fig.savefig(f'{OUT_FIG}/FigureS2_Multivariable_forest.png', dpi=300, bbox_inches='tight')
fig.savefig(f'{OUT_FIG}/FigureS2_Multivariable_forest.tiff', dpi=300, bbox_inches='tight', pil_kwargs={'compression':'tiff_lzw'})
plt.close()
print('  ✓ FigureS2.png + .tiff')

print('\n=== Figuras geradas ===')
for f in sorted(os.listdir(OUT_FIG)):
    print(f'  {OUT_FIG}/{f}')
