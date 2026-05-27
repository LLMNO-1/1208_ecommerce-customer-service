import json
from dataclasses import asdict
from typing import Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from atguigu.infrastructure.llm import llm
from atguigu.domain.state import DialogueState
from atguigu.plan.turn_plan import TurnPlan
from atguigu.prompts.loader import load_prompt
from atguigu.task.flow.flows import FlowsList
from atguigu.prompts.history_builder import HistoryBuilder
from atguigu.knowledge.intents import KnowledgeIntent

class TurnPlanner:
    """
    意图分析器
    作用：根据任务自然语言 调用LLM 分析轨道类型
    """

    async def predict(self,
                      state: DialogueState,
                      #后面的只能关键字传参数
                      *,
                      flows: FlowsList,
                      intents: Dict[str,KnowledgeIntent]) -> TurnPlan:
        """

        :param state:
        :return: 返回值是什么?(分析:定义数据模型)
        """

        # 1. 构建提示词
        inputs_prompt = self._build_inputs_prompt(state, flows,intents)

        # 2. 调用LLM模型
        turn_plan = await  self._predict_from_inputs_prompt(inputs_prompt)

        return turn_plan


    def _build_inputs_prompt(self, state: DialogueState,
                             flows_list: FlowsList,
                             intents:Dict[str,KnowledgeIntent]) -> Dict[str, Any]:
        """
        :param state:
        :return: 字典

        """
        # 1. 用户消息
        user_msg = HistoryBuilder._render_user_message(state.pending_turn.user_message)

        # 2. 历史对话(当前session的turns:后10轮：最近的10轮) 历史对话取多少 取哪些。【策略动态】
        current_conversation = HistoryBuilder.build(state.current_session().turns[-10:])

        # 3. 当前激活任务(业务任务)
        active_task_json = json.dumps(state.active_task.to_dict(),
                                      ensure_ascii=False) if state.active_task is not None else None

        # 4. 中断任务,json.dumps把 Python 的内存对象（如字典、列表、元组等）转换成一个符合 JSON 格式的字符串（String）。
        #整个结果被包裹在了一对单引号里，本质上是一个纯文本字符串
        interrupted_tasks_json = json.dumps([paused_task.to_dict() for paused_task in state.paused_tasks],
                                            ensure_ascii=False)

        # 5. 页面点击卡片获取的信息
        focused_object_json = json.dumps(state.focused_object.to_dict()) if state.focused_object is not None else None

        # 6. 流程清单
        # available_flows_json=[{} for flow in flows_list.flows]
        #先执行什么后执行什么（也就是 steps 里的细节），那是后端执行器（FlowExecutor）的事

        # 7. 知识意图清单
        knowledge_intents_json = json.dumps(
            [{"id": intent.id, "description": intent.description} for intent in intents.values()], ensure_ascii=False)

        available_flows_json = json.dumps(
            {
                #asdict(flow)它负责把上面那种面向对象的结构，变成纯粹的 Python 字典（键值对）
                "flows": [{k: v for k, v in asdict(flow).items() if k != "steps"} for flow in flows_list.flows]
            },
            ensure_ascii=False,
        ),

        return {
            "user_message": user_msg,
            "current_conversation": current_conversation,
            "active_task_json": active_task_json,
            "interrupted_tasks_json": interrupted_tasks_json,
            "focused_object_json": focused_object_json,
            "available_flows_json": available_flows_json,
            "knowledge_intents_json": knowledge_intents_json
        }


    async def _predict_from_inputs_prompt(self, inputs_prompt: Dict[str, Any]) -> TurnPlan:
        """
        1. 加载提示词模板
        2. 格式化模版
        3. 调用模型
        :param inputs_prompt:
        :return:
        """

        prompt_template_text = load_prompt("turn_plan")
        #将纯文本字符串升级为 LangChain 能够识别的 “提示词模板对象”。
        #当你指定为 "jinja2" 时，它会切换到强大的 Jinja2 引擎，允许你在提示词里写 {{ user_message }}
        prompt_template = PromptTemplate.from_template(template=prompt_template_text, template_format="jinja2")
        #前一个组件的输出会自动变成后一个组件的输入
        #JsonOutputParser()（第三棒）：自动接收大模型返回的字符串，利用你刚才学过的反序列化逻辑，把这段 JSON 字符串解析成 Python 字典
        chain = prompt_template | llm | JsonOutputParser()

        llm_response_dict: Dict[str, Any] = await chain.ainvoke(inputs_prompt)

        return TurnPlan.from_dict(llm_response_dict)


if __name__ == '__main__':
    # print(type(json.dumps([])))  # "[]"
    data = [{"name": "zs"}]

    print(json.dumps(data))  # "[{"name": "zs"}]"
