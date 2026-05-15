"""Test-data generation logging utility.

Controls output based on a verbosity level and optionally writes
structured log records to a file.
"""

import os
import logging
from pathlib import Path
from datetime import datetime


class Logger:
    """Verbosity-controlled logging utility.

    Supports three verbosity levels:

    * ``QUIET`` (0) – errors only.
    * ``NORMAL`` (1) – major progress messages.
    * ``VERBOSE`` (2) – full debug information.

    Messages at ``NORMAL`` level and above are printed to stdout.
    All messages are optionally written to a rotating file handler.
    """

    # Verbosity 레벨
    QUIET = 0  # 오류만
    NORMAL = 1  # 주요 진행상황
    VERBOSE = 2  # 모든 디버그 정보

    def __init__(self, verbosity: int = 1, log_file: str = None) -> None:
        """Initialise the logger.

        Args:
            verbosity: Output level – ``0`` quiet, ``1`` normal,
                ``2`` verbose.
            log_file: Optional path to a log file.  Parent directories
                are created automatically.
        """
        self.verbosity = verbosity
        self.file_logger = None

        if log_file:
            # 로그 디렉토리 생성
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # 파일 로거 설정
            self.file_logger = logging.getLogger("test_logger")
            self.file_logger.setLevel(logging.DEBUG)

            # 기존 핸들러 제거 (중복 방지)
            self.file_logger.handlers = []

            # 파일 핸들러 추가
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)

            # 포맷 설정
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)

            self.file_logger.addHandler(file_handler)

    def _log_to_file(self, level: str, message: str) -> None:
        """Write a message to the file logger at the specified level.

        Args:
            level: One of ``"ERROR"``, ``"WARNING"``, ``"INFO"``, or any
                other string (treated as DEBUG).
            message: The log message text.
        """
        if self.file_logger:
            if level == "ERROR":
                self.file_logger.error(message)
            elif level == "WARNING":
                self.file_logger.warning(message)
            elif level == "INFO":
                self.file_logger.info(message)
            else:
                self.file_logger.debug(message)

    def error(self, message: str) -> None:
        """Print an error message and write it to the log file.

        Always outputs regardless of verbosity level.

        Args:
            message: Error message text.
        """
        print(f"[ERROR] {message}")
        self._log_to_file("ERROR", message)

    def info(self, message: str) -> None:
        """Print an informational message at verbosity level 1 or above.

        Args:
            message: Informational message text.
        """
        if self.verbosity >= self.NORMAL:
            print(message)
        self._log_to_file("INFO", message)

    def debug(self, message: str) -> None:
        """Print a debug message at verbosity level 2.

        Args:
            message: Debug message text.
        """
        if self.verbosity >= self.VERBOSE:
            print(message)
        self._log_to_file("DEBUG", message)

    def section(self, title: str) -> None:
        """Print a prominent section header at verbosity level 1 or above.

        Args:
            title: Section title text.
        """
        if self.verbosity >= self.NORMAL:
            print(f"\n{'='*60}")
            print(title)
            print("=" * 60)
        self._log_to_file("INFO", f"=== {title} ===")

    def subsection(self, title: str) -> None:
        """Print a sub-section header at verbosity level 1 or above.

        Args:
            title: Sub-section title text.
        """
        if self.verbosity >= self.NORMAL:
            print(f"\n[{title}]")
        self._log_to_file("INFO", f"[{title}]")

    def success(self, message: str) -> None:
        """Print a success message at verbosity level 1 or above.

        Args:
            message: Success message text.
        """
        if self.verbosity >= self.NORMAL:
            print(f"SUCCESS: {message}")
        self._log_to_file("INFO", f"SUCCESS: {message}")

    def warning(self, message: str) -> None:
        """Print a warning message at verbosity level 1 or above.

        Args:
            message: Warning message text.
        """
        if self.verbosity >= self.NORMAL:
            print(f"WARNING: {message}")
        self._log_to_file("WARNING", message)

    def summary(self, items: dict) -> None:
        """Print a key-value summary at verbosity level 1 or above.

        Args:
            items: Mapping of label strings to values to display.
        """
        if self.verbosity >= self.NORMAL:
            for key, value in items.items():
                print(f"  {key}: {value}")
        self._log_to_file("INFO", "=== Summary ===")
        for key, value in items.items():
            self._log_to_file("INFO", f"  {key}: {value}")


# 전역 로거 인스턴스 (conftest에서 초기화)
logger = None


def init_logger(verbosity: int = 1, log_file: str = None) -> "Logger":
    """Initialise and return the global logger instance.

    Args:
        verbosity: Output level – ``0`` quiet, ``1`` normal, ``2`` verbose.
        log_file: Optional path to a log file.

    Returns:
        The newly created :class:`Logger` instance (also stored as the
        module-level ``logger`` global).
    """
    global logger
    logger = Logger(verbosity, log_file)
    return logger


def get_logger() -> "Logger":
    """Return the global logger instance, creating a default one if needed.

    Returns:
        The current :class:`Logger` instance.
    """
    global logger
    if logger is None:
        logger = Logger(1)  # 기본값
    return logger
