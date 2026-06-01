from dataclasses import asdict

from atguigu.domain.state import DialogueState
from atguigu.task.flow.flows import FlowsList
from atguigu.task.action.runner import ActionRunner, ActionCall, ActionResult
from atguigu.domain.messages import BotMessage
from atguigu.task.flow.steps import FlowStep, StartedFlowStep, CollectedFlowStep, ActionFlowStep, EndFlowStep
from atguigu.task.flow.links import FlowStepStaticLink, FlowStepConditionalLink, FlowStepFallbackLink
from atguigu.domain.contexts import CollectedSystemContext


class FlowExecutor:
    """
    流程执行器：推进yaml中定义的业务任务流程以及系统任务流程
    """

    async def run_task(self,
                       state: DialogueState,
                       flows: FlowsList,
                       action_runner: ActionRunner
                       ):
        """
        推进yaml中定义的业务任务流程以及系统任务流程
        :param state:
        :param flows:
        :param action_runner:
        :return:
        """
        final_messages: list[BotMessage] = []
        while True:  # 找要执行的流程步骤

            # 1. 推进流程（以及内部step）type:类型是action(行动)【action_listen action_response action_xxx】
            action_call: ActionCall = self._advance_until_action(state, flows)

            if action_call.action_name == "action_listen":
                break
            else:
                action_result: ActionResult = await action_runner.run(action_call, state)
                state.set_slots(action_result.slot_updates)
                final_messages.extend(action_result.messages)

        return final_messages

    def _advance_until_action(self,
                              state: DialogueState,
                              flows: FlowsList) -> ActionCall:
        """
        流程推进的核心
        :param state:
        :param flows:
        :return:
        """

        while True:

            # 1. 获取当前时刻的上下文（系统任务流程的上下文以及业务任务流程的上下文）
            current_active_task = state.current_active_task()  # current_active_task:动态改变的（在不同的时刻获取不同的任务流程）

            if current_active_task is None:
                return ActionCall(action_name="action_listen")



            # 2. 获取上下文中的流程Id
            flow_id = current_active_task.flow_id

            # 3. 获取上下文中的流程对象
            flow = flows.get_flow_by_id(flow_id)

            # 4. 获取上下文中的流程对象对应step
            step = flow.get_step_by_id(current_active_task.step_id)

            # 5. 运行当前step
            action_call: ActionCall | None = self._run_step(state, step, flows)

            # 6. 如果step的类型是action,退出while true ,否则就可以继续往下推
            if action_call is not None:
                return action_call

    def _run_step(self, state: DialogueState,
                  step: FlowStep,
                  flows: FlowsList) -> ActionCall | None:
        """
        运行每一个step
        :param state:
        :param step:
        :param flows:
        :return:
        """
        if isinstance(step, StartedFlowStep):
            return self._run_start_step(step, state)
        if isinstance(step, CollectedFlowStep):
            return self._run_collect_slots_step(step, state, flows)
        if isinstance(step, EndFlowStep):
            return self._run_end_step(state)
        if isinstance(step, ActionFlowStep):
            return self._run_action_step(step, state)

    def _run_start_step(self, step: StartedFlowStep,
                        state: DialogueState) -> None:

        # 1. 推进下一步
        self._advance_next_step(state, step)
        # 2. 返回None
        return None

    def _advance_next_step(self, state, step):
        # 1. 寻找下一个step边
        next_step_id = self._select_next_step(step, state)
        # 2. 更新当前任务上下文的step_id(给当前执行任务流程的上下文用)不做这个动作，出不来
        state.current_active_task().step_id = next_step_id

    def _select_next_step(self,
                          step: FlowStep,
                          state: DialogueState
                          ) -> str:

        for link in step.next:
            if isinstance(link, FlowStepStaticLink):
                return link.target  # 下一个边的ID
            if isinstance(link, FlowStepConditionalLink):
                if self._eval_condition(state, link.condition):
                    return link.target
            if isinstance(link, FlowStepFallbackLink):
                return link.target
        return "step not exist next"

    def _eval_condition(self,
                        state: DialogueState,
                        condition: str
                        ) -> bool:
        data = {
            "slots": state.active_task.slots,
            "context": asdict(state.current_active_task())
        }
        return bool(eval(condition, {}, data))

    def _run_end_step(self, state: DialogueState) -> None:
        """
        1. 清空state中系统任务流程上下文
        2. 清空state中业务任务流程上下文
        :param state:
        :return:
        """
        if state.active_system_task:
            state.end_active_system_task()
        else:
            state.end_active_task()
        return None

    def _run_action_step(self,
                         step: ActionFlowStep,
                         state: DialogueState) -> ActionCall:

        self._advance_next_step(state, step)

        return self._build_action_call(state, step)

    def _build_action_call(self, state, step) -> ActionCall:
        # 1. 获取action_name (action_listen/action_response/action_xxx)
        # 2. 获取action_kwargs (构建参数)
        action_name = step.action
        action_kwargs = step.args
        # action_kwargs有可能有:结构有可能是一个str、dict{}  有可能没有:结构是个空字典{}
        if isinstance(action_kwargs, str):
            # "context.response" :response  {}
            action_kwargs = asdict(state.active_system_task)[action_kwargs.split(".")[1]]
        return ActionCall(action_name=action_name, action_kwargs=action_kwargs)

    def _run_collect_slots_step(self,
                                step: CollectedFlowStep,
                                state: DialogueState,
                                flows: FlowsList):

        self._try_to_fill_collect_slot_focused_object(state, step)
        # 1. 判断槽位是否已经填过
        if state.active_task.slots.get(step.slot_name):
            if step.validate:
                if self._eval_condition(state, step.validate.condition):
                    self._advance_next_step(state, step)
                    return None
                else:
                    state.remove_slot(step.slot_name)
                    if step.validate.failure_response:
                        return ActionCall(action_name="action_response",
                                          action_kwargs=asdict(step.validate.failure_response))
                    else:
                        return ActionCall(action_name="action_response",
                                          action_kwargs={"text": "您填写的信息有误，请你重新在填"})
            else:
                self._advance_next_step(state, step)
                return None
        else:
            state.start_active_system_task(CollectedSystemContext(
                flow_id="system_collect_information",
                step_id=flows.get_flow_by_id('system_collect_information').start_step().id,
                slot_name=step.slot_name,
                response=asdict(step.response)
            ))
            return None

    def _try_to_fill_collect_slot_focused_object(self, state: DialogueState,
                                                 step: CollectedFlowStep):

        if state.focused_object is None:
            return None

        if step.slot_name == 'order_number' and state.focused_object.type == "order":
            state.set_slots({step.slot_name: state.focused_object.id})
        if step.slot_name == "product_id" and state.focused_object.type == "product":
            state.set_slots({step.slot_name: state.focused_object.id})



"""好的，我来用 refund_request 流程，逐行代码、逐个数据结构地走完第一轮对话。

  ---
  〇、前置：YAML 加载后在内存中的数据结构

  调用 run_task() 之前，YAML 已经被解析为以下 Python 对象：

  flows（FlowsList）

  FlowsList(
      flows=[
          # ---- 来自 user_flows.yml ----
          Flow(id="onboarding", ...),
          Flow(id="order_status_query", ...),
          Flow(id="logistics_tracking", ...),
          Flow(
              id="refund_request",
              name="退款申请",
              description="帮用户提交简单的退款申请，收集订单号和退款原因。",
              slots=[],
              steps=[
                  StartedFlowStep(
                      id="start",
                      type=FlowStepType.START,
                      next=[FlowStepStaticLink(target="ask_order_number")],
                      description=""
                  ),
                  CollectedFlowStep(
                      id="ask_order_number",
                      type=FlowStepType.COLLECT,
                      slot_name="order_number",
                      response=ResponseDefinition(text="请告诉我你的订单号。", model="static",
  prompt=None),
                      validate=None,
                      next=[FlowStepStaticLink(target="ask_refund_reason")],
                      description=""
                  ),
                  CollectedFlowStep(
                      id="ask_refund_reason",
                      type=FlowStepType.COLLECT,
                      slot_name="refund_reason",
                      response=ResponseDefinition(text="请简单说一下退款原因。", model="static",
  prompt=None),
                      validate=None,
                      next=[FlowStepStaticLink(target="refund_submitted")],
                      description=""
                  ),
                  ActionFlowStep(
                      id="refund_submitted",
                      type=FlowStepType.ACTION,
                      action="action_response",
                      args={"text": "好的，订单{{ slots.order_number }}的退款申请已提交，原因是：{{
  slots.refund_reason }}。后续会尽快为你处理。"},
                      next=[FlowStepStaticLink(target="end")],
                      description=""
                  ),
                  EndFlowStep(
                      id="end",
                      type=FlowStepType.END,
                      next=[],
                      description=""
                  )
              ]
          ),
          Flow(id="similar_product_recommendation", ...),
          Flow(id="human_handoff", ...),

          # ---- 来自 system_flows.yml ----
          Flow(
              id="system_collect_information",
              name="collect information",
              description="Flow for asking the user for a slot value during a collect step",
              slots=[],
              steps=[
                  StartedFlowStep(
                      id="start",
                      type=FlowStepType.START,
                      next=[FlowStepStaticLink(target="ask")],
                      description=""
                  ),
                  ActionFlowStep(
                      id="ask",
                      type=FlowStepType.ACTION,
                      action="action_response",
                      args="context.response",       # ← 注意：这里是 str，不是 dict
                      next=[FlowStepStaticLink(target="listen")],
                      description=""
                  ),
                  ActionFlowStep(
                      id="listen",
                      type=FlowStepType.ACTION,
                      action="action_listen",
                      args={},
                      next=[FlowStepStaticLink(target="end")],
                      description=""
                  ),
                  EndFlowStep(
                      id="end",
                      type=FlowStepType.END,
                      next=[],
                      description=""
                  )
              ]
          ),
          Flow(id="system_task_started", ...),
          Flow(id="system_task_resumed", ...),
          Flow(id="system_cannot_handle", ...),
          Flow(id="system_task_interrupted", ...),
          Flow(id="system_task_canceled", ...),
      ],
      slots={
          "order_number":   FlowSlot(name="order_number",   type="text", label="订单号",
  description="用户的订单号"),
          "order_status":   FlowSlot(name="order_status",   type="text", label="订单状态",
  description="订单当前状态"),
          "order_summary":  FlowSlot(name="order_summary",  type="text", label="订单摘要",
  description="订单摘要信息"),
          "tracking_number":FlowSlot(name="tracking_number", type="text", label="物流单号",
  description="物流单号"),
          "logistics_company": FlowSlot(name="logistics_company", type="text", label="物流公司",
  description="物流公司名称"),
          "logistics_status":FlowSlot(name="logistics_status",type="text", label="物流进度",
  description="物流当前进度"),
          "product_id":     FlowSlot(name="product_id",     type="text", label="商品ID",
  description="当前咨询商品的唯一标识"),
          "refund_reason":  FlowSlot(name="refund_reason",  type="text", label="退款原因",
  description="申请退款的原因"),
      }
  )

  ---
  一、调用 run_task() — 初始完整 state

  用户说"我要退款"，上层意图识别后，已经设置了 active_task，然后调用 run_task()。

  state = DialogueState(
      sender_id="user_001",
      active_task=TaskContext(
          flow_id="refund_request",
          step_id="start",
          slots={}
      ),
      paused_tasks=[],
      active_system_task=None,
      focused_object=None,
      sessions=[
          Session(
              session_id="sess_abc",
              started_at=1716940800.0,
              last_activity_at=1716940800.0,
              closed_at=None,
              turns=[]
          )
      ],
      current_session_id="sess_abc",
      pending_turn=Turn(
          turn_id="turn_001",
          user_message=UserMessage(
              sender_id="user_001",
              message_id="msg_001",
              type=MessageType.TEXT,
              text="我要退款",
              object=None
          ),
          bot_messages=[]
      )
  )

  ---
  二、进入 run_task() — 第 29 行

  # executor.py 第29行
  final_messages: list[BotMessage] = []    # 初始化，空列表

  final_messages = []

  ---
  三、外层 while True 第 1 次迭代 — 第 33 行

  调用 _advance_until_action(state, flows)

  # executor.py 第33行
  action_call: ActionCall = self._advance_until_action(state, flows)

  ---
  四、进入 _advance_until_action() — 内层 while True 第 1 次

  第 57 行：state.current_active_task()

  # state.py 第192行
  def current_active_task(self):
      return self.active_system_task or self.active_task

  # self.active_system_task = None → 假值
  # 返回 self.active_task:
  current_active_task = TaskContext(
      flow_id="refund_request",
      step_id="start",
      slots={}
  )

  第 65 行：取 flow_id

  flow_id = "refund_request"

  第 68 行：flows.get_flow_by_id("refund_request")

  flow = Flow(
      id="refund_request",
      name="退款申请",
      steps=[StartedFlowStep(...), CollectedFlowStep(...), CollectedFlowStep(...),
  ActionFlowStep(...), EndFlowStep(...)]
  )

  第 71 行：flow.get_step_by_id("start")

  step = StartedFlowStep(
      id="start",
      type=FlowStepType.START,
      next=[FlowStepStaticLink(target="ask_order_number")],
      description=""
  )

  第 74 行：_run_step(state, step, flows)

  # 第90行 isinstance 判断
  isinstance(step, StartedFlowStep)  # → True ✓

  第 91 行：调用 _run_start_step(step, state)

  # executor.py 第99-105行
  def _run_start_step(self, step, state) -> None:
      self._advance_next_step(state, step)   # 第103行
      return None                             # 第105行

  第 103 行：_advance_next_step(state, step)

  第 109 行：_select_next_step(step, state)

  # step.next = [FlowStepStaticLink(target="ask_order_number")]
  # 第118-120行:
  for link in step.next:
      if isinstance(link, FlowStepStaticLink):   # → True ✓
          return link.target                      # → return "ask_order_number"

  next_step_id = "ask_order_number"

  第 111 行：更新 step_id

  state.current_active_task().step_id = next_step_id

  # state.current_active_task() → self.active_system_task or self.active_task
  # self.active_system_task 是 None → 返回 self.active_task
  # 所以修改的是 active_task.step_id

  ▎ 📍 state 变化 #1

  state.active_task = TaskContext(
      flow_id="refund_request",
      step_id="ask_order_number",    # ← 从 "start" 变成了 "ask_order_number"
      slots={}
  )
  # 其他字段不变

  _run_start_step 返回 None

  action_call = None

  第 77 行：判断

  if action_call is not None:   # None is not None → False
      return action_call         # 不执行，继续内层 while

  ---
  五、内层 while True 第 2 次

  第 57 行：state.current_active_task()

  # active_system_task 仍是 None → 返回 active_task
  current_active_task = TaskContext(
      flow_id="refund_request",
      step_id="ask_order_number",
      slots={}
  )

  第 65 行

  flow_id = "refund_request"

  第 68 行

  flow = Flow(id="refund_request", ...)   # 同上

  第 71 行：flow.get_step_by_id("ask_order_number")

  step = CollectedFlowStep(
      id="ask_order_number",
      type=FlowStepType.COLLECT,
      slot_name="order_number",
      response=ResponseDefinition(text="请告诉我你的订单号。", model="static", prompt=None),
      validate=None,
      next=[FlowStepStaticLink(target="ask_refund_reason")],
      description=""
  )

  第 74 行：_run_step(state, step, flows)

  isinstance(step, StartedFlowStep)     # → False
  isinstance(step, CollectedFlowStep)   # → True ✓

  第 93 行：调用 _run_collect_slots_step(step, state, flows)

  第 175 行：_try_to_fill_collect_slot_focused_object(state, step)

  # executor.py 第202-211行
  def _try_to_fill_collect_slot_focused_object(self, state, step):
      if state.focused_object is None:   # → True，是 None
          return None                     # 直接返回，什么都没做

  第 177 行：检查槽位

  state.active_task.slots.get(step.slot_name)
  # = state.active_task.slots.get("order_number")
  # = {}.get("order_number")
  # = None → 假值

  第 193 行：进入 else 分支 — 启动系统收集任务

  # executor.py 第194-199行
  state.start_active_system_task(CollectedSystemContext(
      flow_id="system_collect_information",
      step_id=flows.get_flow_by_id('system_collect_information').start_step().id,
      slot_name=step.slot_name,
      response=asdict(step.response)
  ))

  逐步求值：

  # 1. flows.get_flow_by_id('system_collect_information')
  #    → Flow(id="system_collect_information", steps=[StartedFlowStep(id="start",...), ...])

  # 2. .start_step()  → 找第一个 StartedFlowStep
  #    → StartedFlowStep(id="start", ...)

  # 3. .id
  #    → "start"

  # 4. step.slot_name
  #    → "order_number"

  # 5. asdict(step.response)  → 把 ResponseDefinition 转为字典
  #    step.response = ResponseDefinition(text="请告诉我你的订单号。", model="static", prompt=None)
  #    asdict(...) → {"text": "请告诉我你的订单号。", "model": "static", "prompt": None}

  # state.start_active_system_task() 做的事情:
  # self.active_system_task = CollectedSystemContext(...)

  ▎ 📍 state 变化 #2

  state = DialogueState(
      sender_id="user_001",
      active_task=TaskContext(
          flow_id="refund_request",
          step_id="ask_order_number",      # 业务任务停在这里不动
          slots={}                          # 仍然为空
      ),
      paused_tasks=[],
      active_system_task=CollectedSystemContext(   # ← 新增！
          flow_id="system_collect_information",
          step_id="start",
          slot_name="order_number",
          response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
      ),
      focused_object=None,
      sessions=[Session(session_id="sess_abc", started_at=1716940800.0, last_activity_at=1716940800.0,
   closed_at=None, turns=[])],
      current_session_id="sess_abc",
      pending_turn=Turn(turn_id="turn_001", user_message=UserMessage(sender_id="user_001",
  message_id="msg_001", type=MessageType.TEXT, text="我要退款", object=None), bot_messages=[])
  )

  第 200 行：return None

  action_call = None   # 内层 while 继续

  ---
  六、内层 while True 第 3 次

  第 57 行：state.current_active_task()

  # self.active_system_task = CollectedSystemContext(...)  → 不是 None！
  # 直接返回 active_system_task：
  current_active_task = CollectedSystemContext(
      flow_id="system_collect_information",
      step_id="start",
      slot_name="order_number",
      response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  ▎ ⚠️ 从这里开始，推进的是系统流程，不是业务流程！

  第 65 行

  flow_id = "system_collect_information"

  第 68 行

  flow = Flow(
      id="system_collect_information",
      name="collect information",
      steps=[
          StartedFlowStep(id="start", next=[FlowStepStaticLink(target="ask")]),
          ActionFlowStep(id="ask", action="action_response", args="context.response",
  next=[FlowStepStaticLink(target="listen")]),
          ActionFlowStep(id="listen", action="action_listen", args={},
  next=[FlowStepStaticLink(target="end")]),
          EndFlowStep(id="end", next=[])
      ]
  )

  第 71 行：flow.get_step_by_id("start")

  step = StartedFlowStep(
      id="start",
      type=FlowStepType.START,
      next=[FlowStepStaticLink(target="ask")],
      description=""
  )

  第 74 行：_run_step() → StartedFlowStep → _run_start_step()

  _advance_next_step()

  # _select_next_step:
  #   step.next = [FlowStepStaticLink(target="ask")]
  #   → isinstance(link, FlowStepStaticLink) → True
  #   → return "ask"
  next_step_id = "ask"

  # 更新 step_id:
  state.current_active_task().step_id = next_step_id
  # current_active_task() → active_system_task（系统任务优先）

  ▎ 📍 state 变化 #3

  state.active_system_task = CollectedSystemContext(
      flow_id="system_collect_information",
      step_id="ask",                    # ← 从 "start" 变成了 "ask"
      slot_name="order_number",
      response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  # _run_start_step 返回 None → action_call = None → 继续内层 while

  ---
  七、内层 while True 第 4 次

  第 57 行

  current_active_task = CollectedSystemContext(
      flow_id="system_collect_information",
      step_id="ask",
      slot_name="order_number",
      response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  第 65-68 行

  flow_id = "system_collect_information"
  flow = Flow(id="system_collect_information", ...)

  第 71 行：flow.get_step_by_id("ask")

  step = ActionFlowStep(
      id="ask",
      type=FlowStepType.ACTION,
      action="action_response",
      args="context.response",       # ← 字符串！
      next=[FlowStepStaticLink(target="listen")],
      description=""
  )

  第 74 行：_run_step() → ActionFlowStep → _run_action_step(step, state)

  第 155 行：_advance_next_step(state, step)

  # _select_next_step:
  #   step.next = [FlowStepStaticLink(target="listen")]
  #   → return "listen"
  next_step_id = "listen"

  # state.current_active_task() → 仍然是系统任务
  state.active_system_task.step_id = "listen"

  ▎ 📍 state 变化 #4

  state.active_system_task = CollectedSystemContext(
      flow_id="system_collect_information",
      step_id="listen",               # ← 从 "ask" 变成了 "listen"
      slot_name="order_number",
      response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  第 157 行：_build_action_call(state, step)

  # executor.py 第159-168行
  action_name = step.action          # → "action_response"
  action_kwargs = step.args          # → "context.response"（字符串！）

  if isinstance(action_kwargs, str):  # → True ✓
      # asdict(state.active_system_task)["response"]
      #
      # 第1步: asdict(state.active_system_task)
      #   state.active_system_task = CollectedSystemContext(
      #       flow_id="system_collect_information",
      #       step_id="listen",
      #       slot_name="order_number",
      #       response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
      #   )
      #
      #   asdict(...) → {
      #       "flow_id": "system_collect_information",
      #       "step_id": "listen",
      #       "slot_name": "order_number",
      #       "response": {"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
      #   }
      #
      # 第2步: action_kwargs.split(".")[1]
      #   "context.response".split(".") → ["context", "response"]
      #   [1] → "response"
      #
      # 第3步: 取值
      #   {...}["response"] → {"text": "请告诉我你的订单号。", "model": "static", "prompt": None}

      action_kwargs = {"text": "请告诉我你的订单号。", "model": "static", "prompt": None}

  return ActionCall(
      action_name="action_response",
      action_kwargs={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  _run_action_step 返回这个 ActionCall，_advance_until_action 内层 while 退出。

  # 回到 run_task 第33行:
  action_call = ActionCall(
      action_name="action_response",
      action_kwargs={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  ---
  八、外层 while 第 1 次 — 执行 Action（第 35-40 行）

  第 35 行：判断

  if action_call.action_name == "action_listen":
  # "action_response" == "action_listen" → False → 进入 else

  第 38 行：action_runner.run(action_call, state)

  # runner.py
  action_name = action_call.action_name   # "action_response"
  action = self.registry.get("action_response")   # → ActionResponse 实例
  return await action.run(state, action_call.action_kwargs)

  ActionResponse.run() 内部大致做的事情：
  - 读取 action_kwargs["text"] = "请告诉我你的订单号。"
  - 构建一个 BotMessage(text="请告诉我你的订单号。")
  - 返回 ActionResult

  action_result = ActionResult(
      messages=[
          BotMessage(text="请告诉我你的订单号。", object=None)
      ],
      slot_updates={}
  )

  第 39 行：state.set_slots(action_result.slot_updates)

  # state.set_slots({}) → self.active_task.slots.update({}) → 什么都没变

  第 40 行：final_messages.extend(action_result.messages)

  final_messages = [
      BotMessage(text="请告诉我你的订单号。", object=None)
  ]

  ---
  九、外层 while True 第 2 次迭代 — 第 33 行

  调用 _advance_until_action(state, flows)

  ▎ 📍 此时的完整 state（进入第2次外层循环前）：

  state = DialogueState(
      sender_id="user_001",
      active_task=TaskContext(
          flow_id="refund_request",
          step_id="ask_order_number",
          slots={}
      ),
      paused_tasks=[],
      active_system_task=CollectedSystemContext(
          flow_id="system_collect_information",
          step_id="listen",                  # 系统流程停在 listen
          slot_name="order_number",
          response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
      ),
      focused_object=None,
      sessions=[Session(session_id="sess_abc", started_at=1716940800.0, last_activity_at=1716940800.0,
   closed_at=None, turns=[])],
      current_session_id="sess_abc",
      pending_turn=Turn(
          turn_id="turn_001",
          user_message=UserMessage(sender_id="user_001", message_id="msg_001", type=MessageType.TEXT,
  text="我要退款", object=None),
          bot_messages=[]
      )
  )

  内层 while True 第 1 次

  第 57 行

  current_active_task = CollectedSystemContext(
      flow_id="system_collect_information",
      step_id="listen",
      slot_name="order_number",
      response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  第 65-71 行

  flow_id = "system_collect_information"
  flow = Flow(id="system_collect_information", ...)
  step = flow.get_step_by_id("listen")
       = ActionFlowStep(
             id="listen",
             type=FlowStepType.ACTION,
             action="action_listen",
             args={},
             next=[FlowStepStaticLink(target="end")],
             description=""
         )

  第 74 行：_run_step() → ActionFlowStep → _run_action_step(step, state)

  第 155 行：_advance_next_step(state, step)

  # _select_next_step:
  #   step.next = [FlowStepStaticLink(target="end")]
  #   → return "end"
  next_step_id = "end"

  # current_active_task() → 系统任务优先
  state.active_system_task.step_id = "end"

  ▎ 📍 state 变化 #5

  state.active_system_task = CollectedSystemContext(
      flow_id="system_collect_information",
      step_id="end",                  # ← 从 "listen" 变成了 "end"
      slot_name="order_number",
      response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
  )

  第 157 行：_build_action_call(state, step)

  action_name = step.action          # → "action_listen"
  action_kwargs = step.args          # → {}（空字典，不是 str）

  if isinstance(action_kwargs, str):  # → False，是 dict
      pass  # 不进入

  return ActionCall(action_name="action_listen", action_kwargs={})

  退出内层 while，退出 _advance_until_action()。

  ---
  十、外层 while 第 2 次 — 判断（第 35-36 行）

  if action_call.action_name == "action_listen":
  # "action_listen" == "action_listen" → True ✓
      break   # 退出外层 while 循环！

  ---
  十一、run_task() 返回（第 42 行）

  return final_messages

  最终返回值：

  [
      BotMessage(text="请告诉我你的订单号。", object=None)
  ]

  ---
  十二、run_task() 返回后的完整 state

  state = DialogueState(
      sender_id="user_001",
      active_task=TaskContext(
          flow_id="refund_request",
          step_id="ask_order_number",       # 业务任务停在收集订单号
          slots={}                           # 订单号还没收到
      ),
      paused_tasks=[],
      active_system_task=CollectedSystemContext(
          flow_id="system_collect_information",
          step_id="end",                     # 系统流程走到了 end
          slot_name="order_number",
          response={"text": "请告诉我你的订单号。", "model": "static", "prompt": None}
      ),
      focused_object=None,
      sessions=[
          Session(
              session_id="sess_abc",
              started_at=1716940800.0,
              last_activity_at=1716940800.0,
              closed_at=None,
              turns=[]
          )
      ],
      current_session_id="sess_abc",
      pending_turn=Turn(
          turn_id="turn_001",
          user_message=UserMessage(
              sender_id="user_001",
              message_id="msg_001",
              type=MessageType.TEXT,
              text="我要退款",
              object=None
          ),
          bot_messages=[]
      )
  )

  ▎ 上层调用者会把 run_task() 返回的 final_messages 追加到 pending_turn.bot_messages
  ▎ 中，然后把消息发给用户。

  ---
  完整 state 变化时间线

  📍 #0  初始                    active_task.step_id="start"          system_task=None
         │  _run_start_step
  📍 #1  StartStep推进           active_task.step_id="ask_order_number"  system_task=None
         │  _run_collect_slots_step (slot为空)
  📍 #2  启动系统收集任务         active_task不变
  system_task=Created(step_id="start")
         │  系统 _run_start_step
  📍 #3  系统Start推进            active_task不变                       system_task.step_id="ask"
         │  系统 _run_action_step (ask)
  📍 #4  系统Ask推进              active_task不变                       system_task.step_id="listen"
         │  ← ActionCall("action_response") 退出内层循环
         │  action_runner 执行 → BotMessage("请告诉我你的订单号。")
         │
         │  外层第2次 → 再次进入内层
         │  系统 _run_action_step (listen)
  📍 #5  系统Listen推进           active_task不变                       system_task.step_id="end"
         │  ← ActionCall("action_listen") 退出内层循环
         │  action_name == "action_listen" → break 退出外层循环
         │
  ✅     return [BotMessage("请告诉我你的订单号。")]

  第一轮对话中，run_task() 内部共经历了 2 次外层循环、5 次内层推进，state 发生了 5
  次变化，最终向用户输出 1 条消息。
"""


if __name__ == '__main__':
    condition = "context.get('reason') == 'clarification_rejected'"
    data = {
        "context": {"reason": "abc"}
    }

    print(bool(eval(condition, {}, data)))
