import json
#而 AsyncSession 允许程序在等待数据库响应的同时，去处理其他用户的请求
from sqlalchemy.ext.asyncio import AsyncSession
#它让你不用写原生的字符串 SQL 语句（比如 SELECT * FROM users），而是用面向对象（Python 代码）的方式来构建查询
from sqlalchemy import select
#专门针对 MySQL 数据库优化的 INSERT 插入语句构建器
from sqlalchemy.dialects.mysql import insert  # 小小
from atguigu.domain.state import DialogueState
from atguigu.model.dialogue_state_record import DialogueStateRecord


class DialogueStateRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load(self, sender_id: str) -> DialogueState:
        """
        读操作
        :return:
        """

        # 1. 定义sql
        sql = select(DialogueStateRecord).where(DialogueStateRecord.sender_id == sender_id)

        # 2. 执行sql
        result = await self.session.execute(sql)

        # 3. 获取结果
        sate = result.scalar_one_or_none()

        if sate:
            state_dict = json.loads(sate.state_json)
            return DialogueState.from_dict(state_dict)

        return DialogueState(sender_id=sender_id)

    async def save(self, dialogue_state: DialogueState):
        """
        写操作(插入、修改)
        传统：插入之前先查询该条件（sender_id）对应的记录是否存在，如果不存在 则插入，反之修改
        进阶：负责将插入sql直接升级为修改sql(主键重复机制判断)
        :return:
        """

        # 1. 得到DialogueState的json字符串
        #将字典序列化为文本字符串，以便存入数据库的 TEXT 或 JSON 类型的字段中
        state_json: str = json.dumps(dialogue_state.to_dict())

        # 2. 定义插入的sql语句
        insert_stmt = insert(DialogueStateRecord).values(
            sender_id=dialogue_state.sender_id, state_json=state_json
        )

        # 3. 升级update语句的sql，如果冲突就更新”的智能语句
        update_stmt = insert_stmt.on_duplicate_key_update(
            state_json=insert_stmt.inserted.state_json
        )

        # 4. 执行sql，它负责将 SQLAlchemy 的对象（update_stmt）翻译成真正的 MySQL 字符串语句并执行
        await  self.session.execute(update_stmt)

        # 5. 提交
        #如果在第 4 步或之前程序崩溃了，数据库会自动回滚（Rollback），仿佛什么都没发生过。
        #只有当执行了 await session.commit()，数据才算彻底安全落地
        await self.session.commit()
