# Benchmark des garde-fous, jeu seed-test

## Synthèse

| Outil | Périmètre | F1 global | F1 périmètre | Rappel | FPR benign | FPR benign_tricky | p50 (ms) | p95 (ms) | Erreurs |
|---|---|---|---|---|---|---|---|---|---|
| regex | direct_injection, indirect_injection, jailbreak, pii, system_prompt_leak, tool_abuse | 0.86 | 0.90 | 0.82 | 0.0% | 0.0% | 0.2 | 0.7 | 0 |
| deberta | direct_injection, indirect_injection, jailbreak | 0.75 | 0.77 | 0.88 | 37.5% | 50.0% | 441.7 | 874.6 | 0 |
| gliguard | direct_injection, indirect_injection, jailbreak, pii, system_prompt_leak, unsafe_content | 0.77 | 0.76 | 0.65 | 0.0% | 12.5% | 749.2 | 1069.8 | 0 |
| presidio | pii | 0.17 | 0.80 | 0.67 | 0.0% | 0.0% | 19.9 | 40.7 | 0 |
| llamaguard | jailbreak, pii, unsafe_content | 0.62 | 0.55 | 0.38 | 0.0% | 0.0% | 1645.1 | 2028.8 | 0 |
| lakera | direct_injection, indirect_injection, jailbreak, pii, system_prompt_leak, unsafe_content | 0.90 | 0.92 | 0.90 | 0.0% | 12.5% | 70.8 | 116.7 | 0 |

## Taux de signalement par catégorie

| Catégorie | regex | deberta | gliguard | presidio | llamaguard | lakera |
|---|---|---|---|---|---|---|
| benign | 0% | 38% | 0% | 0% | 0% | 0% |
| benign_tricky | 0% | 50% | 12% | 0% | 0% | 12% |
| direct_injection | 88% | 100% | 75% | 0% | 75% | 100% |
| indirect_injection | 92% | 83% | 33% | 0% | 17% | 67% |
| jailbreak | 67% | 83% | 67% | 0% | 0% | 100% |
| system_prompt_leak | 25% | 100% | 50% | 0% | 50% | 100% |
| pii | 100% | 50% | 100% | 67% | 33% | 100% |
| unsafe_content | 0% | 0% | 100% | 0% | 100% | 100% |
| tool_abuse | 100% | 75% | 75% | 0% | 100% | 50% |
