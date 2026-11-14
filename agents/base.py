"""Common agent plumbing: register tools as Semantic Kernel plugin, call them, trace them."""
from llm import get_kernel

try:
    from semantic_kernel.functions import kernel_function
except Exception:
    def kernel_function(**kw):
        return lambda f: f


class BaseAgent:
    name = "agent"
    plugin_name = "plugin"

    def __init__(self, plugin):
        self.plugin = plugin
        self.kernel = get_kernel()
        if self.kernel is not None:
            self.kernel.add_plugin(plugin, plugin_name=self.plugin_name)

    async def tool(self, rec, fn: str, **kw):
        via = "direct"
        if self.kernel is not None:
            try:
                out = (await self.kernel.invoke(plugin_name=self.plugin_name,
                                                function_name=fn, **kw)).value
                via = "kernel"
            except Exception as e:
                out = getattr(self.plugin, fn)(**kw)
                via = f"direct (kernel error {type(e).__name__})"
        else:
            out = getattr(self.plugin, fn)(**kw)
        rec.post(self.name, f"tool:{fn}", {"args": kw, "result": out, "via": via})
        return out
