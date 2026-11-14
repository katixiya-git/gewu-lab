"""AI 对话模块的内部实现。

这个包里放的全是「跟模型打交道」的零件，按一次对话的执行顺序读最顺：

1. ``llm.py`` / ``client.py``：拿到模型客户端（一个是 LangChain 封装，
   一个是裸 OpenAI SDK，前者给对话图用，后者给 embedding 用）；
2. ``prompts.py``：系统提示词，决定模型的角色、能做什么、怎么说话；
3. ``tools.py``：8 个工具背后的业务查询（查实验室、查空档、校验预约……）；
4. ``agent_tools.py``：把上面的函数包装成 LangGraph 能识别的「工具」；
5. ``graph.py``：把模型和工具连成「模型 ↔ 工具」循环的图；
6. ``runtime.py``：图的进程级单例，负责连 Redis 存对话上下文。

对外入口在 ``app.services.ai_service``（负责跑图、拼事件），
HTTP 路由在 ``app.api.routes.ai``。
"""
