"""파이프라인 도메인 예외. 각 예외가 자기 HTTP 코드를 들고 있어서 라우터에서 try/except를
반복하지 않고 main.py에 등록한 핸들러 한 곳이 모든 변환을 처리한다."""


class PipelineError(Exception):
    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NodeNotFound(PipelineError):
    status_code = 404


class Conflict(PipelineError):
    status_code = 409


class InvalidRequest(PipelineError):
    status_code = 422
