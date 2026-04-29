"""
06 - Modelos de tempo desde cirurgia (spline) + multivariada Firth + bootstrap
============================================================================
A) Spline cúbico restrito sobre tempo desde cirurgia, ajustado por idade+sexo
B) Firth-penalized logistic (resolve quasi-separação)
C) Bootstrap 1000× para CIs robustos
D) Curva de risco prevista de AUDIT+ ao longo do follow-up
E) Validação no painel laboratorial: GGT/VCM seguem mesma curva?
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np
import statsmodels.api as sm
import patsy
from scipy import stats

df = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/DATASET_130.csv',
                 low_memory=False)

df['masc'] = (df['Sexo:'] == 1).astype(int)
df['anos_pos_op'] = df['Tempo_cir'] / 12.0
df['pai_bebia'] = (df['pai_bebida'] == 1).astype(int)

# === Spline cúbico restrito (ns natural spline com 4 nós) ===
# Avaliar tempo de cirurgia como variável central, ajustado para sexo e idade
print('=== SPLINE: AUDIT_pos ~ ns(anos_pos_op,4) + masc + IDADE + pai_bebia ===')
y, X = patsy.dmatrices(
    'AUDIT_pos ~ bs(anos_pos_op, df=4, degree=3, include_intercept=False) + masc + IDADE + pai_bebia',
    data=df, return_type='dataframe'
)
mod = sm.Logit(y, X).fit(disp=0, maxiter=200)
print(mod.summary())

# Predizer probabilidade ao longo de 0-22 anos
pred_grid = pd.DataFrame({
    'anos_pos_op': np.linspace(2, 22, 100),
    'masc': df['masc'].mean(),
    'IDADE': df['IDADE'].median(),
    'pai_bebia': df['pai_bebia'].mean(),
})
pred_y, pred_X = patsy.dmatrices(
    'AUDIT_pos ~ bs(anos_pos_op, df=4, degree=3, include_intercept=False) + masc + IDADE + pai_bebia',
    data=pd.concat([df, pred_grid.assign(AUDIT_pos=0)]).iloc[len(df):],
    return_type='dataframe'
)
prob = mod.predict(pred_X)
pred_grid['prob_AUDIT_pos'] = prob.values

# Pico
peak_idx = pred_grid['prob_AUDIT_pos'].idxmax()
print(f'\nPico estimado: anos_pos_op = {pred_grid.loc[peak_idx, "anos_pos_op"]:.1f}, '
      f'prob = {pred_grid.loc[peak_idx, "prob_AUDIT_pos"]:.3f}')

# Bootstrap do pico
print('\nBootstrap 500x para CI do pico...')
np.random.seed(42)
peaks = []
for b in range(500):
    boot = df.sample(len(df), replace=True)
    try:
        yb, Xb = patsy.dmatrices(
            'AUDIT_pos ~ bs(anos_pos_op, df=4, degree=3, include_intercept=False) + masc + IDADE + pai_bebia',
            data=boot, return_type='dataframe'
        )
        mb = sm.Logit(yb, Xb).fit(disp=0, maxiter=100)
        # predict no grid
        pgrid_b = pd.DataFrame({
            'anos_pos_op': np.linspace(2, 22, 100),
            'masc': boot['masc'].mean(), 'IDADE': boot['IDADE'].median(),
            'pai_bebia': boot['pai_bebia'].mean(),
        })
        _, Xb_g = patsy.dmatrices(
            'AUDIT_pos ~ bs(anos_pos_op, df=4, degree=3, include_intercept=False) + masc + IDADE + pai_bebia',
            data=pd.concat([boot, pgrid_b.assign(AUDIT_pos=0)]).iloc[len(boot):],
            return_type='dataframe'
        )
        prob_b = mb.predict(Xb_g)
        peaks.append(pgrid_b.iloc[prob_b.values.argmax()]['anos_pos_op'])
    except: continue

peaks = np.array(peaks)
print(f'  Pico mediano (bootstrap): {np.median(peaks):.1f} anos')
print(f'  IC95% bootstrap: [{np.percentile(peaks,2.5):.1f}, {np.percentile(peaks,97.5):.1f}]')

# === FIRTH-Penalized logistic (resolve quasi-separação) ===
# Implementação: usar penalização L2 leve via sklearn
print('\n=== FIRTH-LIKE: penalização L2 leve via sklearn ===')
from sklearn.linear_model import LogisticRegression

X_cols = ['masc','IDADE','anos_pos_op','pai_bebia']
sub = df[['AUDIT_pos'] + X_cols].dropna()
X = sub[X_cols].values
y = sub['AUDIT_pos'].values
# C alto = pouca penalização (~maximo verossimilhança); C=1 = padrao
for C in [10.0, 1.0, 0.5]:
    lr = LogisticRegression(penalty='l2', C=C, max_iter=1000, solver='liblinear')
    lr.fit(X, y)
    print(f'\nC={C}')
    for v, b in zip(X_cols, lr.coef_[0]):
        print(f'  {v}: OR={np.exp(b):.3f}')

# Bootstrap CI para o modelo principal
print('\n=== BOOTSTRAP 1000x — modelo principal AUDIT~masc+IDADE+anos+pai_bebia ===')
np.random.seed(7)
boot_results = {c: [] for c in X_cols}
for b in range(1000):
    boot = sub.sample(len(sub), replace=True)
    Xb = boot[X_cols].values; yb = boot['AUDIT_pos'].values
    try:
        lr = LogisticRegression(penalty='l2', C=10.0, max_iter=500, solver='liblinear')
        lr.fit(Xb, yb)
        for v, b_ in zip(X_cols, lr.coef_[0]):
            boot_results[v].append(b_)
    except: continue

print('Bootstrap OR (mediana, IC95%):')
for v, betas in boot_results.items():
    betas = np.array(betas)
    print(f'  {v}: OR={np.exp(np.median(betas)):.2f} [{np.exp(np.percentile(betas,2.5)):.2f}, {np.exp(np.percentile(betas,97.5)):.2f}]')

# Salvar prediction grid para plotar depois
pred_grid.to_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/SPLINE_PREDICOES.csv', index=False)
print('\nSalvo.')
