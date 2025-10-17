from langchain_core.language_models.chat_models import SimpleChatModel

class LLMDefault(SimpleChatModel):
    """Defaul LLM, replying a constant string. Used before a proper one is added."""

    @property
    def _llm_type(self):
        return ""

    def _call(self, *args, **kwargs):
        return "You did not configure a Language Model. Do it in the settings!"

    async def _acall(self, *args, **kwargs):
        return "You did not configure a Language Model. Do it in the settings!"
    
    def bind_tools(self, *args, **kwargs):
        return self