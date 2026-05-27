#
# import uvicorn
# from atguigu.config.config import settings
#
# if __name__ == '__main__':
#     uvicorn.run(app="api.app:app", host=settings.app_host, port=settings.app_port)

import asyncio
import uvicorn

from atguigu.config.config import settings

if __name__ == "__main__":
    # 1. 手动创建配置
    config = uvicorn.Config(
        app="api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        loop="asyncio"  # 强制指定使用标准 asyncio 循环
    )
    # 2. 实例化服务器
    server = uvicorn.Server(config)

    # 3. 绕过 uvicorn.run 内部的 asyncio_run，直接用标准事件循环运行
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.serve())