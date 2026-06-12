from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    oda_converter_path: str | None
    oda_output_version: str
    max_upload_mb: int
    temp_dir: str | None

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            oda_converter_path=os.environ.get("ODA_CONVERTER_PATH"),
            oda_output_version=os.environ.get("ODA_OUTPUT_VERSION", "ACAD2013"),
            max_upload_mb=int(os.environ.get("MAX_UPLOAD_MB", "50")),
            temp_dir=os.environ.get("TEMP_DIR"),
        )
