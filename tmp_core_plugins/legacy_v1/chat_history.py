
from cat.mad_hatter.decorators import hook
from cat.types import ChatRequest, Message, TextContent

from .convo import UserMessage


@hook(priority=-1000)
def fast_reply(_, cat):

    if not isinstance(cat.request, ChatRequest):
        # legacy `user_message_json`
        user_message_json = UserMessage.model_validate(cat.request)
        # Impose user_id as the one authenticated
        # (ws message may contain a fake id)
        user_message_json.user_id = cat.user_id

        cat.request = ChatRequest(
            messages = [
                Message(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=user_message_json.text
                    )
                )
            ]
            # TODOV2 support images in the v1 format

            # TODOV2 load history from working memory as in v1
        )

        # make available the good ol' user message in wm
        cat.working_memory.user_message_json = user_message_json


@hook(priority=-1000)
def before_cat_sends_message(mex, cat):
    mex.type = "chat"
    mex.content = mex.text
    return mex


#  TODOV2: WAS IN WORKING MEMORY
#     MAX_WORKING_HISTORY_LENGTH = 20
#
#     history: List[ConversationMessage] = [] # TODOV2: should redirect to UserMessage.messages?
#     user_message_json: Optional[UserMessage] = None
#
#     def update_history(self, message: ConversationMessage):
#         """
#         Adds a message to the history.
#
#         Parameters
#         ----------
#         message : ConversationMessage
#             The message, must be of type `ConversationMessage` (typically a subclass like `UserMessage` or `CatMessage`).
#         """
#         self.history.append(message)
#         self.history = self.history[-MAX_WORKING_HISTORY_LENGTH:]

    # def stringify_chat_history(self, latest_n: int = 20) -> str:
    #     """Serialize chat history.
    #     Converts to text the recent conversation turns.
    #     Useful for retrocompatibility with old non-chat models, and to easily insert convo into a prompt without using dedicated objects and libraries.

    #     Parameters
    #     ----------
    #     latest_n : int
    #         How many latest turns to stringify.

    #     Returns
    #     -------
    #     history : str
    #         String with recent conversation turns.
    #     """

    #     history = self.history[-latest_n:]

    #     history_string = ""
    #     for turn in history:
    #         history_string += f"\n - {turn.who}: {turn.text}"

    #     return history_string


    # def langchainfy_chat_history(self, latest_n: int = 20) -> List[BaseMessage]: 
    #     """Convert chat history in working memory to langchain objects.

    #     Parameters
    #     ----------
    #     latest_n : int
    #         How many latest turns to convert.

    #     Returns
    #     -------
    #     history : List[BaseMessage]
    #         List of langchain HumanMessage / AIMessage.
    #     """
        
    #     recent_history = self.history[-latest_n:]
    #     langchain_chat_history = []

    #     for message in recent_history:
    #         langchain_chat_history.append(
    #             message.langchainfy()    
    #         )

    #     return langchain_chat_history


# TODOV2 update_history was called:
"""
# just after `before_cat_sends_message` in StrayCat.__call__
# update conversation history (Human turn)
self.working_memory.update_history(
    self.working_memory.user_message_json
)

# inside StrayCat.send_chat_message
# see commented code there

# before return final_output in StrayCat.__call__
"""