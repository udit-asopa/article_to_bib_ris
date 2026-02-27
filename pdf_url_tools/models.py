from dataclasses import dataclass
from pathlib import Path
from typing import Literal


StatusFilter = Literal["ok", "bad"]


@dataclass(frozen=True)
class UrlCheckResult:
    url: str
    is_valid: bool
    reason: str
    redirected_links: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineConfig:
    pdf: Path
    output: Path | None
    check: bool
    timeout: float
    workers: int
    status: StatusFilter | None
    report_output: Path | None
    export: bool
