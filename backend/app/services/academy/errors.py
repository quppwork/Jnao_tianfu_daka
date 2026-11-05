"""学院领域错误。API 层只负责转成 HTTP。"""


class AcademyError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
