"""Size of the context the LLM receives: top_k passages per dev question, chosen config.

Run from the repository root with the retrieval settings of the shipped config:
PYTHONPATH=src VIGIE_QDRANT_PATH=data/cache/qdrant python docs/proofs/J8/eval/context_size.py
Prints, over the dev questions, the words of the passages handed to the prompt and the
prompt itself as built by vigie.rag.prompt, plus the share of prompts that exceed
llm_num_ctx when counted at 1.5 tokens per French word (a rough rule, no tokenizer of the
LLM is loaded here).
"""

import statistics

from vigie.config import Settings
from vigie.evaluation.golden import load_golden
from vigie.rag.prompt import build_messages
from vigie.retrieval.factory import open_retriever

TOKENS_PER_WORD = 1.5

settings = Settings()
questions = [q for q in load_golden(settings.golden_path) if q.split == "dev"]
passage_words: list[int] = []
prompt_words: list[int] = []
longest: list[int] = []
with open_retriever(settings) as retriever:
    for q in questions:
        found = retriever.search(q.question, settings.top_k)
        words = [len(p.text.split()) for p in found]
        passage_words.append(sum(words))
        longest.append(max(words, default=0))
        prompt = "\n".join(m.content for m in build_messages(q.question, found))
        prompt_words.append(len(prompt.split()))

over = sum(w * TOKENS_PER_WORD > settings.llm_num_ctx for w in prompt_words)
print(f"dev questions: {len(questions)}, top_k={settings.top_k}, num_ctx={settings.llm_num_ctx}")
print(
    f"passage words per question: median {statistics.median(passage_words):.0f}, "
    f"max {max(passage_words)}"
)
print(f"longest single passage: median {statistics.median(longest):.0f} words, max {max(longest)}")
print(
    f"prompt words: median {statistics.median(prompt_words):.0f}, max {max(prompt_words)}; "
    f"estimated tokens median {statistics.median(prompt_words) * TOKENS_PER_WORD:.0f}"
)
print(f"prompts over num_ctx at {TOKENS_PER_WORD} tokens per word: {over} of {len(questions)}")
