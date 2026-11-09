"""ClassifierDescriptionGenerator — черновик описания класса (SETUP-13).

Исходное дерево (Классификатор.md → seed/classifier/asu_v1.txt) содержит
только названия узлов, без пояснений — такие классы, как "DNN", без
контекста непонятны ни человеку, редактирующему промпты, ни маленькой
LLM, которая по ним классифицирует. Узкая задача: по названию узла и
его пути в дереве сформировать краткое объяснение термина.

Черновик НЕ сохраняется автоматически — возвращается вызывающему на
review (человек читает/правит и сохраняет через обычный
PATCH .../nodes/{id}), в соответствии с принципом проекта "выводы LLM —
это предположения".
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from schemas.common.defaults import DEFAULT_LLM_MODEL

from fe_bot.llm_gateway.client import LLMGateway

_DEFAULT_MODEL = DEFAULT_LLM_MODEL


class _DescriptionDraft(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)


_PROMPT_TEMPLATE = """\
Ты — эксперт по автоматизированным системам управления (АСУ) и смежным
техническим областям (обработка данных, анализ обстановки, машинное
обучение).

Класс классификатора «{name}» находится в дереве по пути:
{path}

Напиши РОВНО ОДНО краткое предложение на русском языке, объясняющее,
что означает этот класс/термин в данном контексте — так, чтобы
человек, не знакомый с сокращением или узким термином, понял, о чём
речь. Если название — аббревиатура, обязательно расшифруй её. Не
выдумывай факты, которых не можешь знать: если значение неоднозначно,
опиши наиболее вероятное значение в данном техническом домене.

Верни СТРОГО валидный JSON без markdown-разметки, комментариев и
текста до/после:

{{
  "description": "..."
}}
"""


class ClassifierDescriptionGenerator:
    def __init__(self, *, llm_gateway: LLMGateway, model: str = _DEFAULT_MODEL) -> None:
        self._gateway = llm_gateway
        self._model = model

    def generate(self, *, name: str, path: list[str]) -> str:
        """Может бросить LLMUnavailableError / InvalidLLMOutputError — caller решает."""
        prompt = _PROMPT_TEMPLATE.format(name=name, path=" → ".join(path))
        result = self._gateway.generate_structured(
            prompt=prompt,
            schema=_DescriptionDraft,
            model=self._model,
            temperature=0.2,
        )
        return result.parsed.description
