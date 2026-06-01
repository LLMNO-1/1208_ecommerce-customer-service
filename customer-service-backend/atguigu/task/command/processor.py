from typing import List

from atguigu.domain.contexts import TaskContext, StartedSystemContext, InterruptedSystemContext, ResumedSystemContext, \
    CanceledSystemContext
from atguigu.domain.state import DialogueState
from atguigu.task.command.models import Command, StartFlowCommand, SetSlotsCommand, ResumeFlowCommand, CancelFlowCommand
from atguigu.task.flow.flows import FlowsList


class CommandProcessor:
    """
    命令处理器
    """

    def run(self,
            state: DialogueState,
            commands: List[Command],
            flow_list: FlowsList
            ) -> None:
        for command in commands:
            self._apply(state, command=command, flow_list=flow_list)

    def _apply(self, state: DialogueState, *, command: Command, flow_list: FlowsList):

        if isinstance(command, StartFlowCommand):
            self._handle_start_flow(state, command, flow_list)  # 最复杂
        elif isinstance(command, SetSlotsCommand):
            self._handle_set_slots(state, command)  # 最简单
        elif isinstance(command, ResumeFlowCommand):
            self._handle_resume_flow(state, flow_list, command)  # 其次复杂
        elif isinstance(command, CancelFlowCommand):
            self.handle_cancel_flow(state, flow_list)
        else:
            pass

    def _handle_set_slots(self, state: DialogueState,
                          command: SetSlotsCommand):

        if state.active_task is not None:
            state.set_slots(command.slots)  # 文本消息过来：llm填写槽位{"order_number":"111"} 对象消息过来的：自己填写的槽位{"order_number":"111"}

    def _handle_start_flow(self,
                           state: DialogueState,
                           command: StartFlowCommand,
                           flow_list: FlowsList):
        """
        开启业务任务：1)
        业务任务的流程ID: command.flow
        业务任务的流程名字：_readable_flow_name()
        :param state:
        :param command:
        :param flow_list:
        :return:
        """
        # 0.  系统流程情况
        state.end_active_system_task()
        # 0.1 判断开启的流程是否是系统流程
        if command.flow.startswith("system_"):
            raise ValueError(f"不能开启系统流程流程ID: {command.flow}")
        # 0.2 判断流程是否存在
        flow = flow_list.get_flow_by_id(command.flow)
        if flow is None:
            raise ValueError(f"开启的流程ID: {command.flow} 对应的流程不存在")

        target_flow = flow_list.get_flow_by_id(command.flow)

        # 1. 开启一个新业务任务的时候，先判断当前有没有业务任务(是不是就是你 是你 不用管 不是你，中断别人)
        active_task = state.active_task

        # 1.1 当前已经有业务任务
        if active_task is not None:
            # a) 开启的业务任务当前已经在执行
            if active_task.flow_id == command.flow:
                return  # 不用重复开

            # b) 当前正在执行的业务任务不是要开启的业务任务
            # b.1) 中断别人
            state.interrupted_active_task()
            interrupted_flow_id = active_task.flow_id
            interrupted_flow_name = self._readable_flow_name(active_task.flow_id, flow_list)

            # b.2) 检查自己是否在栈中
            # ①：栈中没你 需要新开，引出中断开场白
            if not state.resumed_active_task(command.flow):
                started_flow_id = command.flow
                started_flow_name = self._readable_flow_name(command.flow, flow_list)

                state.start_active_task(TaskContext(
                    flow_id=target_flow.id,
                    step_id=target_flow.start_step().id
                ))
            # ②：栈中有你（之前存的状态是怎样，就是怎样）不用重复开，引出中断开场白
            else:

                started_flow_id = command.flow
                started_flow_name = self._readable_flow_name(command.flow, flow_list)

            # b.2) 引出中断系统流程(中断信息的过场出来)：别人存在
            self._activate_interrupted_system_task(state, flow_list,
                                                   interrupted_flow_id=interrupted_flow_id,
                                                   interrupted_flow_name=interrupted_flow_name,
                                                   started_flow_id=started_flow_id,
                                                   started_flow_name=started_flow_name
                                                   )

            return

        # 1.2 当前没有业务任务（活跃）
        # 栈中有你（之前存的状态是怎样，就是怎样）不用重复开.不需要开启的过长表
        resumed = state.resumed_active_task(command.flow)  # 试着恢复同名任务
        if resumed:
            self._activate_resumed_system_flow(
                state, flow_list,
                resumed_flow_id=command.flow,
                resumed_flow_name=self._readable_flow_name(command.flow, flow_list),
            )
            return
        # 栈中没你 需要新开，引出开启系统流程的开场白
        state.start_active_task(TaskContext(
            flow_id=target_flow.id,
            step_id=target_flow.start_step().id
        ))
        # 激活系统流程（开启系统流程的任务）
        self._activate_start_system_task(state,
                                         flow_list,
                                         started_flow_id=command.flow,
                                         started_flow_name=self._readable_flow_name(command.flow, flow_list))

    @staticmethod
    def _readable_flow_name(flow_id: str, flow_list: FlowsList) -> str:

        flow = flow_list.get_flow_by_id(flow_id)

        return flow.name if flow.name else flow.id

    @staticmethod
    def _activate_start_system_task(state: DialogueState,
                                    flow_list: FlowsList,
                                    *,
                                    started_flow_id: str,
                                    started_flow_name: str
                                    ):

        flow = flow_list.get_flow_by_id("system_task_started")

        state.start_active_system_task(StartedSystemContext(
            flow_id=flow.id,
            step_id=flow.start_step().id,
            started_flow_id=started_flow_id,
            started_flow_name=started_flow_name
        ))

    @staticmethod
    def _activate_interrupted_system_task(state: DialogueState,
                                          flow_list: FlowsList,
                                          *,
                                          interrupted_flow_id: str,
                                          interrupted_flow_name: str,
                                          started_flow_id: str,
                                          started_flow_name: str
                                          ):

        flow = flow_list.get_flow_by_id("system_task_interrupted")
        state.start_active_system_task(InterruptedSystemContext(
            flow_id=flow.id,
            step_id=flow.start_step().id,
            interrupted_flow_id=interrupted_flow_id,
            interrupted_flow_name=interrupted_flow_name,
            started_flow_id=started_flow_id,
            started_flow_name=started_flow_name
        ))

    def _activate_resumed_system_flow(self,
                                      state: DialogueState,
                                      flow_list: FlowsList,
                                      resumed_flow_id: str,
                                      resumed_flow_name: str):

        flow = flow_list.get_flow_by_id("system_task_resumed")
        state.start_active_system_task(ResumedSystemContext(
            flow_id=flow.id,
            step_id=flow.start_step().id,
            resumed_flow_id=resumed_flow_id,
            resumed_flow_name=resumed_flow_name
        ))

    def _activate_cancel_system_flow(self,
                                     state: DialogueState,
                                     flow_list: FlowsList,
                                     *,
                                     cancel_flow_id: str,
                                     cancel_flow_name: str):

        flow = flow_list.get_flow_by_id("system_task_canceled")
        state.start_active_system_task(CanceledSystemContext(
            flow_id=flow.id,
            step_id=flow.start_step().id,
            canceled_flow_id=cancel_flow_id,
            canceled_flow_name=cancel_flow_name
        ))

    def handle_cancel_flow(self,
                           state: DialogueState,
                           flow_list: FlowsList):

        """
        取消当前业务流程、进入取消系统流程
        :param state:
        :param flow_list:
        :return:
        """

        # 1. 激活系统的取消流程
        task = state.active_task
        flow = flow_list.get_flow_by_id(task.flow_id)
        self._activate_cancel_system_flow(state,
                                          flow_list,
                                          cancel_flow_id=flow.id,
                                          cancel_flow_name=self._readable_flow_name(flow.id, flow_list)
                                          )
        state.end_active_task()

    def _handle_resume_flow(self,
                            state: DialogueState,
                            flow_list: FlowsList,
                            command: ResumeFlowCommand):

        # ===== 第一步:确定要恢复哪个流程 =====
        if command.flow is not None:
            # 指名恢复:用户明确说了恢复哪个
            target_flow = flow_list.get_flow_by_id(command.flow)
            if target_flow is None:
                raise ValueError(f"Unknown flow '{command.flow}'.")
            target_flow_id = target_flow.id
            target_flow_name = target_flow.name
        else:
            # 不指名恢复:用户只说"继续刚才的" → 取暂停栈栈顶(最近挂起的)
            if not state.paused_tasks:
                return
            top_paused = state.paused_tasks[-1]
            target_flow_id = top_paused.flow_id
            target_flow_name = self._readable_flow_name(target_flow_id, flow_list)

        # ===== 第二步:按"当前有没有活跃任务"恢复 =====
        active_task = state.active_task

        if active_task is not None:

            # 判断恢复的任务流程ID是否等于当前正在执行的业务任务流程ID
            if active_task.flow_id == target_flow_id:
                return

            state.interrupted_active_task()  # 将当前正在执行的业务任务流程压入栈
            interrupted_flow_id = active_task.flow_id
            interrupted_flow_name = self._readable_flow_name(active_task.flow_id, flow_list)

            if not state.resumed_active_task(flow_id=target_flow_id):  # 恢复失败了
                state.resumed_active_task()  # 撤销影响的那个当前正在执行的业务任务流程
                return

            self._activate_interrupted_system_task(
                state, flow_list,
                interrupted_flow_id=interrupted_flow_id,
                interrupted_flow_name=interrupted_flow_name,
                started_flow_id=target_flow_id,
                started_flow_name=target_flow_name,
            )
        else:
            if not state.resumed_active_task(command.flow):  # ④没任务,直接恢复
                return

            resumed = state.active_task  # 获取从栈中恢复的业务流程
            self._activate_resumed_system_flow(
                state, flow_list,
                resumed_flow_id=resumed.flow_id,
                resumed_flow_name=self._readable_flow_name(resumed.flow_id, flow_list),
            )


"""
DialogueState (对话状态)
  ├── active_task: TaskContext | None    ← 当前正在执行的业务任务
  ├── paused_tasks: list[TaskContext]    ← 被中断暂存的业务任务栈
  └── active_system_task: SystemContext | None ← 当前执行的系统流程

  TaskContext (业务任务上下文)
  ├── flow_id: str     ← 如 "order_status_query"
  ├── step_id: str     ← 如 "start"
  └── slots: dict      ← 如 {"order_number": "A20240315001"}

  关键概念：
  - 业务任务 = 用户真正想做的事（查订单、退款等）
  - 系统流程 = 框架自动插入的"过场动画"（开启提示、中断提示、恢复提示等）
  - paused_tasks 是一个栈，被中断的任务压入栈中，恢复时从栈中弹出

第1轮：全新开启（分支 1.2 + 栈中无你）

  用户说"帮我查一下订单状态"，LLM 返回：
  command = StartFlowCommand(command="start_flow", flow="order_status_query")

  当前状态：
  active_task = None
  paused_tasks = []

  步骤 0：关闭当前系统流程

  state.end_active_system_task()  # active_system_task = None
  先把上一个系统流程清掉（当前没有，所以无事发生）。

  步骤 0.1：检查是否是系统流程

  if command.flow.startswith("system_"):
      raise ValueError(...)
  "order_status_query" 不以 "system_" 开头，通过。

  步骤 0.2：检查流程是否存在

  flow = flow_list.get_flow_by_id("order_status_query")  # 从流程注册表中查找
  假设存在，拿到 flow 对象。

  步骤 1：走哪个分支？

  active_task = state.active_task  # None
  因为 active_task is None，跳过分支 1.1，进入分支 1.2（当前没有业务任务）。

  分支 1.2：尝试从栈中恢复

  resumed = state.resumed_active_task("order_status_query")
  看 resumed_active_task 的逻辑：
  def resumed_active_task(self, flow_id):
      if not self.paused_tasks:      # 栈是空的 → return False
          return False
      ...
  paused_tasks = []，所以直接返回 False，栈中没你。

  栈中没你 → 全新开启

  state.start_active_task(TaskContext(
      flow_id="order_status_query",
      step_id="start"        # 流程的起始步骤
  ))
  此时状态变为：
  active_task = TaskContext(flow_id="order_status_query", step_id="start", slots={})

  激活"开启系统流程"（开场白）

  self._activate_start_system_task(state, flow_list,
      started_flow_id="order_status_query",
      started_flow_name="订单状态查询")
  这个函数查找 system_task_started 系统流程，设置 active_system_task：
  state.start_active_system_task(StartedSystemContext(
      flow_id="system_task_started",
      step_id="start",
      started_flow_id="order_status_query",
      started_flow_name="订单状态查询"
  ))

  第1轮结束后的状态：

  active_task = TaskContext(flow_id="order_status_query", ...)
  paused_tasks = []
  active_system_task = StartedSystemContext(started_flow_name="订单状态查询", ...)

  效果：系统流程会渲染一段开场白，比如"好的，我来帮您查询订单状态~"，然后进入订单状态查询的业务流程。

  ---
  第2轮：中断别人（分支 1.1 + 栈中无你）

  用户说"我要退款"，LLM 返回：
  command = StartFlowCommand(command="start_flow", flow="refund")

  当前状态（从第1轮继承）：
  active_task = TaskContext(flow_id="order_status_query", ...)
  paused_tasks = []

  步骤 0 ~ 0.2：同上，检查通过。

  步骤 1：走哪个分支？

  active_task = state.active_task  # 不是 None！是 order_status_query
  进入分支 1.1（当前已经有业务任务）。

  分支 1.1-a：是不是同一个流程？

  if active_task.flow_id == command.flow:
      # "order_status_query" == "refund" ? → False，不return

  分支 1.1-b：中断别人

  state.interrupted_active_task()
  这个函数做了：
  def interrupted_active_task(self):
      self.paused_tasks.append(self.active_task)  # 把 order_status_query 压入暂停栈
      self.active_task = None                      # 清空活跃任务

  状态变为：
  active_task = None
  paused_tasks = [TaskContext(flow_id="order_status_query", ...)]  ← 被中断的

  检查自己在不在栈中

  if not state.resumed_active_task("refund"):
  resumed_active_task("refund") 遍历 paused_tasks：
  - paused_tasks[0].flow_id = "order_status_query" ≠ "refund" → 找不到，返回 False

  所以 not False = True，进入 ①：栈中没你，需要新开：
  state.start_active_task(TaskContext(
      flow_id="refund",
      step_id="start"
  ))
  状态变为：
  active_task = TaskContext(flow_id="refund", ...)
  paused_tasks = [TaskContext(flow_id="order_status_query", ...)]

  引出中断系统流程

  self._activate_interrupted_system_task(state, flow_list,
      interrupted_flow_id="order_status_query",    # 被中断的老任务
      interrupted_flow_name="订单状态查询",
      started_flow_id="refund",                    # 新开启的任务
      started_flow_name="退款"
  )
  设置 active_system_task：
  InterruptedSystemContext(
      flow_id="system_task_interrupted",
      interrupted_flow_id="order_status_query",
      interrupted_flow_name="订单状态查询",
      started_flow_id="refund",
      started_flow_name="退款"
  )

  第2轮结束后的状态：

  active_task = TaskContext(flow_id="refund", ...)
  paused_tasks = [TaskContext(flow_id="order_status_query", ...)]  ← 订单查询在栈里等着
  active_system_task = InterruptedSystemContext(...)

  效果：系统流程会渲染一段中断过渡语，比如"订单状态查询已暂停，现在为您处理退款~"。

  ---
  第3轮：恢复栈中任务（分支 1.1 + 栈中有你）

  用户说"算了，还是继续查订单吧"，LLM 返回：
  command = StartFlowCommand(command="start_flow", flow="order_status_query")

  当前状态（从第2轮继承）：
  active_task = TaskContext(flow_id="refund", ...)
  paused_tasks = [TaskContext(flow_id="order_status_query", ...)]

  步骤 0 ~ 0.2：检查通过。

  分支 1.1-a：是不是同一个流程？

  # "refund" == "order_status_query" ? → False

  分支 1.1-b：中断当前的 refund

  state.interrupted_active_task()
  状态变为：
  active_task = None
  paused_tasks = [
      TaskContext(flow_id="order_status_query", ...),  ← 之前就在栈里
      TaskContext(flow_id="refund", ...)               ← 刚压入的
  ]

  分支 1.1-b-②：检查自己在不在栈中

  if not state.resumed_active_task("order_status_query"):
  resumed_active_task("order_status_query") 遍历：
  - paused_tasks[0].flow_id = "order_status_query" → 找到了！

  它执行：
  self.active_task = paused_task           # 恢复为活跃任务
  del self.paused_tasks[0]                 # 从栈中删除
  return True

  状态变为：
  active_task = TaskContext(flow_id="order_status_query", step_id=之前保存的step, slots=之前保存的slots)
  paused_tasks = [TaskContext(flow_id="refund", ...)]

  not True = False，所以走 ②：栈中有你，不用重复开：
  # 不调用 state.start_active_task()，直接用恢复出来的任务
  started_flow_id = "order_status_query"
  started_flow_name = "订单状态查询"

  引出中断系统流程

  self._activate_interrupted_system_task(state, flow_list,
      interrupted_flow_id="refund",              # 被中断的退款
      interrupted_flow_name="退款",
      started_flow_id="order_status_query",      # 恢复的订单查询
      started_flow_name="订单状态查询"
  )

  第3轮结束后的状态：

  active_task = TaskContext(flow_id="order_status_query", step_id=恢复的step, slots=恢复的slots)
  paused_tasks = [TaskContext(flow_id="refund", ...)]  ← 退款在栈里等着
  active_system_task = InterruptedSystemContext(...)

  效果：订单状态查询从栈中恢复了之前保存的状态（包括已填的槽位和当前步骤），退款被压入栈底。系统流程渲染"退款已暂停，继
  续为您查询订单状态~"。

   一图总结

  新请求来了
      │
      我在服务谁？
     ┌────┴────┐
    没人        有人
     │           │
     │      ┌────┴────┐
     │    同一个人？  不同人？
     │      │           │
     │   什么都不做   让当前人等一等
     │   (return)      │
     │            ┌────┴────┐
     │         新来的     新来的
     │       之前等过？   没等过？
     │           │           │
     │     从等候本叫回来   重新招呼坐下
     │     (保留之前进度)  (从第一步开始)
     │           │           │
     └─────┬─────┴─────┬─────┘
           │           │
        最后说一句合适的过渡语
        （"好的" / "稍等" / "继续"）
"""