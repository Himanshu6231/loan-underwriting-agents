"""Semantic Kernel setup. Groq is used through its OpenAI-compatible endpoint."""
import os

USE_LLM = bool(os.getenv("GROQ_API_KEY")) and os.getenv("USE_LLM", "1") == "1"
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

try:
    from semantic_kernel import Kernel
    SK_OK = True
except Exception:  # SK not installed -> tools still run directly (see agents/base.py)
    Kernel, SK_OK = None, False

_kernel = None


def get_kernel():
    global _kernel
    if not SK_OK:
        return None
    if _kernel is None:
        _kernel = Kernel()
        if USE_LLM:
            from openai import AsyncOpenAI
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
            client = AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"],
                                 base_url="https://api.groq.com/openai/v1")
            _kernel.add_service(OpenAIChatCompletion(
                service_id="groq", ai_model_id=MODEL, async_client=client))
    return _kernel


async def ask(system: str, user: str):
    """One LLM call via the Semantic Kernel chat service. Returns None if LLM is off/fails."""
    if not USE_LLM or not SK_OK:
        return None
    try:
        from semantic_kernel.contents import ChatHistory
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
        svc = get_kernel().get_service("groq")
        hist = ChatHistory(system_message=system)
        hist.add_user_message(user)
        out = await svc.get_chat_message_content(
            chat_history=hist,
            settings=OpenAIChatPromptExecutionSettings(temperature=0, max_tokens=400))
        return str(out)
    except Exception:
        return None
