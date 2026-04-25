import platform
import subprocess
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    logger.warning("psutil not installed — RAM detection will fall back to sysctl")
    _HAS_PSUTIL = False


@dataclass
class HardwareInfo:
    cpu_brand: str
    ram_gb: float
    is_apple_silicon: bool

    @property
    def recommendation(self) -> dict[str, Any]:
        if self.is_apple_silicon and self.ram_gb >= 16:
            return {
                "can_run_local_llm": True,
                "recommended_model": "llama3.1:8b",
                "setup_command": "brew install ollama && ollama pull llama3.1:8b",
                "note": f"Apple Silicon with {self.ram_gb:.0f}GB RAM — great for local inference.",
            }
        if self.is_apple_silicon and self.ram_gb >= 8:
            return {
                "can_run_local_llm": True,
                "recommended_model": "mistral:7b-q4",
                "setup_command": "brew install ollama && ollama pull mistral:7b-q4",
                "note": f"Apple Silicon with {self.ram_gb:.0f}GB RAM — use quantized model.",
            }
        if self.ram_gb >= 16:
            return {
                "can_run_local_llm": True,
                "recommended_model": "mistral:7b-q4",
                "setup_command": "docker compose --profile local-llm up -d",
                "note": "Linux/Windows — use the local-llm Docker profile (requires NVIDIA GPU).",
            }
        return {
            "can_run_local_llm": False,
            "recommended_model": "claude-3-5-haiku",
            "setup_command": "",
            "note": "Limited RAM — recommend cloud LLM. Configure API key in Settings.",
        }


def detect_hardware() -> HardwareInfo:
    cpu_brand = platform.processor() or platform.machine()
    is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"

    if _HAS_PSUTIL:
        ram_bytes = psutil.virtual_memory().total
        ram_gb = ram_bytes / (1024 ** 3)
    else:
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            ram_gb = int(out.strip()) / (1024 ** 3)
        except Exception:
            ram_gb = 8.0

    info = HardwareInfo(cpu_brand=cpu_brand, ram_gb=ram_gb, is_apple_silicon=is_apple_silicon)
    logger.info("Hardware detected: cpu=%s ram_gb=%.1f apple_silicon=%s", cpu_brand, ram_gb, is_apple_silicon)
    return info
