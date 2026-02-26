from typing import List, Dict, TYPE_CHECKING
from cat.protocols.future.llm_wrapper import LLMWrapper
from cat import utils, log

if TYPE_CHECKING:
    from cat.types import Message
    from cat.mad_hatter.decorators import Tool


class LLMMixin:
    """Mixin for LLM interaction methods (generation, classification)."""

    async def llm(
        self,
        system_prompt: str,
        model: str | None = None,
        messages: list["Message"] = [],
        tools: list["Tool"] = [],
        stream: bool = True,
    ) -> "Message":
        """Generate a response using the Large Language Model."""

        # TODOV2: re-introduce request-level model override (via settings or task args)
        if model:
            slug = model
        elif self.model:
            slug = self.model
        else:
            raise Exception("No LLM specified for generation.")

        # Get LLM instance from CheshireCat
        model = await self.ccat.get_llm(slug, self.request)

        new_mex: Message = await LLMWrapper.invoke(
            self,
            model=model,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            stream=stream
        )
        return new_mex
    
    async def classify(
        self, sentence: str, labels: List[str] | Dict[str, List[str]], score_threshold: float = 0.5
    ) -> str | None:
        """Classify a sentence."""

        if isinstance(labels, dict):
            labels_names = labels.keys()
            examples_list = "\n\nExamples:"
            for label, examples in labels.items():
                for ex in examples:
                    examples_list += f'\n"{ex}" -> "{label}"'
        else:
            labels_names = labels
            examples_list = ""

        labels_list = '"' + '", "'.join(labels_names) + '"'

        prompt = f"""Classify this sentence:
"{sentence}"

Allowed classes are:
{labels_list}{examples_list}

"{sentence}" -> """

        response = (await self.llm(prompt)).text

        best_label, score = min(
            ((label, utils.levenshtein_distance(response, label)) for label in labels_names),
            key=lambda x: x[1],
        )

        return best_label if score < score_threshold else None
