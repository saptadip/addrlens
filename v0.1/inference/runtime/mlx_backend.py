"""Apple Silicon dev backend (mlx-lm). Verbatim mechanics from
phase3/server.py:{_load_llm, summarize_impressions, explain_card}."""
from __future__ import annotations

DEFAULT_MODEL_ID = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"


class MlxBackend:
    def __init__(self, model_id: str = DEFAULT_MODEL_ID):
        # Lazy import — mlx-lm is Apple-Silicon only; importing on Linux fails.
        from mlx_lm import load
        self.model_id = model_id
        self.model, self.tokenizer = load(model_id)

    def generate_from_messages(
        self,
        msgs: list[dict],
        max_tokens: int,
        temp: float,
        top_p: float,
        repetition_penalty: float,
    ) -> str:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors
        sampler = make_sampler(temp=temp, top_p=top_p)
        logits_procs = make_logits_processors(repetition_penalty=repetition_penalty)
        prompt = self.tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True)
        return generate(
            self.model, self.tokenizer, prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler, logits_processors=logits_procs,
            verbose=False,
        ).strip()
