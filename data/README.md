# Estudo Álcool Arruda — Datasets Anonimizados

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
