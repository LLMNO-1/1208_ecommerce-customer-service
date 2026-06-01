from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from atguigu.infrastructure.llm import llm
from atguigu.domain.messages import UserMessage, BotMessage
from atguigu.domain.state import Turn
from atguigu.prompts.history_builder import HistoryBuilder
from atguigu.prompts.loader import  load_prompt
from atguigu.knowledge.provider import KnowledgeChunk


class KnowledgeResponder:

    async def respond(self,
                      user_message: UserMessage,
                      recent_turns: list[Turn],
                      chunks: list[KnowledgeChunk]
                      ) -> list[BotMessage]:
        # 准备提示词上下文
        user_message = HistoryBuilder._render_user_message(user_message)
        history = HistoryBuilder.build(recent_turns)
        """
        history = "USER: [label=商品对象, id=prod_2024001, title=华为Mate60 Pro 256GB 雅丹黑, attributes=price=6999
  url=https://img.example.com/mate60pro.jpg brand=华为 category=手机]\nBOT: 您正在查看华为Mate60 Pro 256GB
  雅丹黑，售价6999元，请问有什么可以帮您？"
        """
        knowledge_content = "\n\n".join([chunk.content for chunk in chunks])
        """
        knowledge_content = "未检索到相关问题\n\n未检索到相关信息"
        """

        # 构造chain
        prompt_text = load_prompt("knowledge_respond")
        prompt = PromptTemplate.from_template(
            prompt_text,
            template_format="jinja2"
        )
        chain = prompt | llm | StrOutputParser()

        # 运行chain
        response = await chain.ainvoke({
            "user_message": user_message,
            "history": history,
            "knowledge_content": knowledge_content,
        })
        """
          response = await chain.ainvoke({
      "user_message": "这件商品的退货政策是什么",
      "history": "USER: [label=商品对象, id=prod_2024001, ...]\nBOT: 您正在查看华为Mate60 Pro 256GB 雅丹黑...",
      "knowledge_content": "未检索到相关问题\n\n未检索到相关信息",
  })
        """

        return [BotMessage(text=response)]
