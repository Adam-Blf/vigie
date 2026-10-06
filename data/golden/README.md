# Golden set

`questions.jsonl` holds 80 reference questions over the four regulations, each verified
against the Cellar text by a second author. `test.sha256` seals the test split: the
validator refuses the file if a test row changes without a new seal.

| category | dev | test | total |
|---|---|---|---|
| in_scope | 40 | 20 | 60 |
| out_of_scope | 7 | 3 | 10 |
| trap | 7 | 3 | 10 |
| total | 54 | 26 | 80 |

## Which rows each figure uses

Published retrieval and citation figures are computed on the sealed test split only, as
stated in `eval/thresholds.yaml`.

`correct_refusal_rate` is the exception: it is measured on all 10 out-of-scope rows, dev
and test together. The stratified split leaves only 3 of them in test, so a rate on test
alone could only take the values 0, 1/3, 2/3 and 1, and one missed refusal would move it
by 33 points. The floor itself does not change: 0.90, at least 9 correct refusals out of
10. For that reason the 7 dev out-of-scope rows must not be used to tune the refusal
prompt or threshold: they are part of the gate.
