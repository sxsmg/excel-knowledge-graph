from .config import Settings

_cfg = Settings()

if _cfg.LLM_PROVIDER == "openai":
    from llama_index.llms.openai import OpenAI as _LLM
    llm = _LLM(model=_cfg.LLM_MODEL, api_key=_cfg.LLM_API_KEY, temperature=0)
else:
    # minimal Gemini wrapper, swap with google-generativeai SDK
    import google.generativeai as genai
    genai.configure(api_key=_cfg.LLM_API_KEY)
    from llama_index.llms.vertex_ai import Vertex as _LLM  # or custom wrapper
    llm = _LLM(model_name=_cfg.LLM_MODEL, temperature=0)
