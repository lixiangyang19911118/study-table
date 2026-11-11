"""业务异常基类。

「用户这次操作不被允许」全部抛它，由 main.py 一个处理器统一转成
JSON 响应并带上 code。路由层不必逐条 try/except —— 十二条状态边
各写一遍捕获，迟早漏一条变成 500。

core 层，只 import 标准库，不认识任何业务模型。
"""


class BizError(Exception):
    """带 code 与 HTTP 状态码的业务异常。

    code 供前端分辨具体原因，不要拿 detail 文本做判断 ——
    文案随时会改，code 不会。
    """

    def __init__(self, message: str, code: str = "bad_request", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
