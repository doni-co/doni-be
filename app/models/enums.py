import enum


class AssetKind(str, enum.Enum):
    DATASET = "dataset"
    MEDIA_SET = "media_set"


class AssetStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    READY = "ready"
    FAILED = "failed"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class NodeRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class AssetOrigin(str, enum.Enum):
    UPLOAD = "upload"
    NODE_OUTPUT = "node_output"


class UploadStatus(str, enum.Enum):
    STORED = "stored"              # 파일 저장 완료, 분류 전
    CLASSIFIED = "classified"      # dataset/media_set 등록 완료
    UNSUPPORTED = "unsupported"    # 분류 실패 (확장자 미지원 등)
    FAILED = "failed"              # 파일 저장 자체가 실패
