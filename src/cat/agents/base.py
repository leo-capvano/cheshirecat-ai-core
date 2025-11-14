from abc import ABC, abstractmethod

class BaseAgent(ABC):

    async def list_tools(self):
        return await self.cat.list_tools()
    
    @property
    def chat_request(self):
        return self.cat.chat_request
    
    @abstractmethod
    async def execute(self, cat):
        pass
