import enum


class AssetKind(str, enum.Enum):
    DATASET = "dataset"
    MEDIASET = "mediaset"


class AssetStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    READY = "ready"
    FAILED = "failed"


class AssetOrigin(str, enum.Enum):
    UPLOAD = "upload"
    NODE_OUTPUT = "node_output"


class UploadStatus(str, enum.Enum):
    STORED = "stored"              # 파일 저장 완료, 분류 전
    CLASSIFIED = "classified"      # Asset 등록 완료
    UNSUPPORTED = "unsupported"    # 분류 실패 (확장자 미지원 등)
    FAILED = "failed"              # 파일 저장 자체가 실패
    INVALID = "invalid"            # 파일은 저장됐지만 내용을 읽을 수 없음 (정형 파일 파싱 실패)


class NodeRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
