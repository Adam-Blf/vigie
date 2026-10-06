# Benchmark des garde-fous, jeu deepset-test

## Synthèse

| Outil | Périmètre | F1 global | F1 périmètre | Rappel | FPR benign | FPR benign_tricky | p50 (ms) | p95 (ms) | Erreurs |
|---|---|---|---|---|---|---|---|---|---|
| regex | direct_injection, indirect_injection, jailbreak, pii, system_prompt_leak, tool_abuse | 0.06 | 0.06 | 0.03 | 0.0% | 0.0% | 0.1 | 1.1 | 0 |
| deberta | direct_injection, indirect_injection, jailbreak | 0.54 | 0.54 | 0.37 | 0.0% | 0.0% | 331.3 | 676.6 | 0 |
| gliguard | direct_injection, indirect_injection, jailbreak, pii, system_prompt_leak, unsafe_content | 0.49 | 0.49 | 0.33 | 3.6% | 0.0% | 586.8 | 929.1 | 0 |
| presidio | pii | 0.00 | 0.00 | 0.00 | 0.0% | 0.0% | 27.0 | 81.8 | 0 |
| llamaguard | jailbreak, pii, unsafe_content | 0.23 | 0.00 | 0.00 | 3.6% | 0.0% | 1533.0 | 2798.4 | 0 |
| lakera | direct_injection, indirect_injection, jailbreak, pii, system_prompt_leak, unsafe_content | 0.88 | 0.88 | 0.88 | 8.3% | 0.0% | 66.8 | 75.0 | 96 |

## Taux de signalement par catégorie

| Catégorie | regex | deberta | gliguard | presidio | llamaguard | lakera |
|---|---|---|---|---|---|---|
| benign | 0% | 0% | 4% | 0% | 4% | 8% |
| benign_tricky |  |  |  |  |  |  |
| direct_injection | 3% | 37% | 33% | 0% | 13% | 88% |
| indirect_injection |  |  |  |  |  |  |
| jailbreak |  |  |  |  |  |  |
| system_prompt_leak |  |  |  |  |  |  |
| pii |  |  |  |  |  |  |
| unsafe_content |  |  |  |  |  |  |
| tool_abuse |  |  |  |  |  |  |
