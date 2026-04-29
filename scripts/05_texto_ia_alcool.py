"""
05 - Análise quantitativa do texto narrativo IA para sinal de álcool
====================================================================
Para cada um dos 1.869 pacientes da Arruda, extrair sinal textual sobre álcool.

Estratégia em camadas:
  L1 - Keywords brutas (etilismo, álcool, cerveja, vinho etc.) — proxy bruta
  L2 - Pareamento contextual (regex):
       - "consome ... cerveja ... [N] doses"
       - "nega etilismo" => negativo explícito
       - "alcoolismo" => positivo claro
       - "social", "ocasional" => baixo
  L3 - Score: 0=nega/sem menção; 1=ocasional/social; 2=consumo regular; 3=AUD/alcoolismo

Validar contra os 130 com gold AUDIT/CAGE: matriz de confusão, sens/esp/PPV/NPV
para detecção de AUDIT≥8 e CAGE≥1.

Saída:
  trabalho/dados/TEXTO_IA_SCORE.csv
  trabalho/resultados/05_texto_ia_validacao.md
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd, numpy as np, re, unicodedata
from sklearn.metrics import confusion_matrix, roc_auc_score, classification_report

def norm(s):
    if pd.isna(s) or s is None: return ''
    s = str(s).lower().strip()
    s = re.sub(r'#l\b', '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-z\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# Carrega texto IA
ia = pd.read_csv('Y:/Estudos_Arruda_Galvao/03_DADOS_BRUTOS_AUDITORIA/arruda_prontuario/BASE_PARA_IA_v2.csv',
                 usecols=['PACIENTEID','NOME','TEXTO_COMORBIDADES'], low_memory=False)
ia['n'] = ia['NOME'].apply(norm)
ia['txt'] = ia['TEXTO_COMORBIDADES'].fillna('').apply(lambda x: unicodedata.normalize('NFKD', str(x).lower()).encode('ascii','ignore').decode('ascii'))
print(f'Pacientes na IA: {len(ia)}')

# === Padrões regex ===
RE_NEGA = re.compile(r'\b(nega|nao bebe|nao etilista|nao alcoo|abstemia?o?|sem etilismo|sem alcool|abstenc)\b[^.]{0,40}(etilismo|alcool|bebida|alcoolista)?', re.I)
RE_AUD  = re.compile(r'\b(alcoolism[oa]|etilist[ao]|alcoolatra|abuso de alcool|dependencia (alcoolica|de alcool))\b', re.I)
RE_QUANT_HIGH = re.compile(r'(\d+\s*(latas?|garrafas?|copos?|doses?))\s*(de|por)?\s*(cerveja|vinho|cachaca|destilados?|whisky)?', re.I)
RE_REGULAR = re.compile(r'\b(toma|bebe|consome)\s+\w*\s*(cerveja|vinho|whisky|cachaca|drink)\s+\w*\s*(diari|semanal|sabado|domingo|fim de seman|todo|frequent|rotina)', re.I)
RE_SOCIAL = re.compile(r'\b(social|ocasional|raramente|esporadic|festas?|eventos?)\w*\b', re.I)
RE_MENTION = re.compile(r'\b(alcool|cerveja|vinho|cachaca|destilad|whisky|drinks?|etilis|bebida)\w*\b', re.I)

def score_texto(t):
    """Retorna (label, raw_features)."""
    t = t.lower()
    feats = {
        'has_mention': bool(RE_MENTION.search(t)),
        'has_nega': bool(RE_NEGA.search(t)),
        'has_aud': bool(RE_AUD.search(t)),
        'has_quant_high': bool(RE_QUANT_HIGH.search(t)),
        'has_regular': bool(RE_REGULAR.search(t)),
        'has_social': bool(RE_SOCIAL.search(t)),
    }
    # Heurística:
    if feats['has_aud']:
        s = 3
    elif feats['has_quant_high'] or feats['has_regular']:
        s = 2
    elif feats['has_social']:
        s = 1
    elif feats['has_nega']:
        s = 0
    elif feats['has_mention']:
        # mencao sem qualificacao - assumir baixo (1)
        s = 1
    else:
        s = 0
    return s, feats


scores = []
for _, row in ia.iterrows():
    s, feats = score_texto(row['txt'])
    scores.append({'PACIENTEID': row['PACIENTEID'], 'NOME': row['NOME'], 'n': row['n'],
                   'TXT_SCORE': s, **feats})
sc = pd.DataFrame(scores)
print('\nDistribuição TXT_SCORE:')
print(sc['TXT_SCORE'].value_counts().sort_index())

# === Validação contra os 130 ===
df130 = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/DATASET_130.csv',
                   low_memory=False)
df130['n'] = df130['NOME'].apply(norm)

merged = df130.merge(sc, on='n', how='left')
print(f'\n130 com score IA: {merged["TXT_SCORE"].notna().sum()}')

# Distribuição score IA por AUDIT_pos
print('\n=== TXT_SCORE × AUDIT_pos ===')
ct = pd.crosstab(merged['TXT_SCORE'], merged['AUDIT_pos'], margins=True)
print(ct)
print('\n=== TXT_SCORE × CAGE_pos ===')
print(pd.crosstab(merged['TXT_SCORE'], merged['CAGE_pos'], margins=True))

# === Validação binária: TXT_SCORE >= 2 (regular/AUD) prevê AUDIT+ ===
val = merged[['TXT_SCORE','AUDIT_pos','CAGE_pos']].dropna()
val['ia_pos_2'] = (val['TXT_SCORE'] >= 2).astype(int)
val['ia_pos_3'] = (val['TXT_SCORE'] >= 3).astype(int)

for label, col in [('TXT≥2 → AUDIT+', ('ia_pos_2','AUDIT_pos')),
                   ('TXT≥3 → AUDIT+', ('ia_pos_3','AUDIT_pos')),
                   ('TXT≥2 → CAGE+', ('ia_pos_2','CAGE_pos')),
                   ('TXT≥3 → CAGE+', ('ia_pos_3','CAGE_pos'))]:
    yhat, y = col
    cm = confusion_matrix(val[y], val[yhat])
    if cm.shape == (2,2):
        tn, fp, fn, tp = cm.ravel()
        sens = tp/(tp+fn) if tp+fn else 0
        esp  = tn/(tn+fp) if tn+fp else 0
        ppv  = tp/(tp+fp) if tp+fp else 0
        npv  = tn/(tn+fn) if tn+fn else 0
        try:
            auc = roc_auc_score(val[y], val[yhat])
        except: auc = np.nan
        print(f'\n{label}')
        print(f'  TP={tp} FP={fp} FN={fn} TN={tn}')
        print(f'  Sens={sens:.2f} Esp={esp:.2f} PPV={ppv:.2f} NPV={npv:.2f} AUC={auc:.2f}')

# AUC do score contínuo
sub = val.dropna()
print('\n=== AUC TXT_SCORE contínuo ===')
print(f'  AUDIT+: AUC = {roc_auc_score(sub["AUDIT_pos"], sub["TXT_SCORE"]):.3f}')
print(f'  CAGE+: AUC = {roc_auc_score(sub["CAGE_pos"], sub["TXT_SCORE"]):.3f}')

sc.to_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/TEXTO_IA_SCORE.csv', index=False)
merged.to_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/DATASET_130_COM_TXT_IA.csv', index=False)
print('\nSalvos.')

# === Combinação Texto + Lab ===
print('\n=== ENSEMBLE: TXT_SCORE + GGT_med ===')
# Pega bioquímica
bio = pd.read_csv('Y:/Estudos_Arruda_Galvao/Estudo Alcool Arruda/trabalho/dados/BIOQUIMICA_PERPATIENT.csv',
                  low_memory=False)
m = merged[['n','AUDIT_pos','CAGE_pos','TXT_SCORE']].merge(
    bio[['n','GGT_med','GGT_max','VCM_med']], on='n', how='left'
)
sub = m.dropna(subset=['TXT_SCORE','GGT_med','AUDIT_pos'])
print(f'  N com texto + GGT: {len(sub)}')
import statsmodels.api as sm
X = sm.add_constant(sub[['TXT_SCORE','GGT_med']])
mod = sm.Logit(sub['AUDIT_pos'], X).fit(disp=0)
print('Modelo:')
print(pd.DataFrame({'OR':np.exp(mod.params),'p':mod.pvalues}).to_string())

# AUC do score combinado
sub['linpred'] = mod.predict(X)
print(f'\nAUC combinado TXT+GGT: {roc_auc_score(sub["AUDIT_pos"], sub["linpred"]):.3f}')
print(f'AUC só TXT: {roc_auc_score(sub["AUDIT_pos"], sub["TXT_SCORE"]):.3f}')
print(f'AUC só GGT: {roc_auc_score(sub["AUDIT_pos"], sub["GGT_med"]):.3f}')
