"""
테스트 데이터 생성 로깅 유틸리티
verbosity 레벨에 따라 출력을 제어하고 파일에 로그를 기록
"""

import os
import logging
from pathlib import Path
from datetime import datetime


class Logger:
    """로깅 유틸리티 클래스"""

    # Verbosity 레벨
    QUIET = 0  # 오류만
    NORMAL = 1  # 주요 진행상황
    VERBOSE = 2  # 모든 디버그 정보

    def __init__(self, verbosity=1, log_file=None):
        """
        Args:
            verbosity: 로그 레벨 (0: QUIET, 1: NORMAL, 2: VERBOSE)
            log_file: 로그 파일 경로 (선택)
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

    def _log_to_file(self, level, message):
        """파일에 로그 기록"""
        if self.file_logger:
            if level == "ERROR":
                self.file_logger.error(message)
            elif level == "WARNING":
                self.file_logger.warning(message)
            elif level == "INFO":
                self.file_logger.info(message)
            else:
                self.file_logger.debug(message)

    def error(self, message):
        """항상 표시되는 오류 메시지"""
        print(f"[ERROR] {message}")
        self._log_to_file("ERROR", message)

    def info(self, message):
        """레벨 1 이상: 주요 정보"""
        if self.verbosity >= self.NORMAL:
            print(message)
        self._log_to_file("INFO", message)

    def debug(self, message):
        """레벨 2: 상세 디버그 정보"""
        if self.verbosity >= self.VERBOSE:
            print(message)
        self._log_to_file("DEBUG", message)

    def section(self, title):
        """섹션 헤더 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"\n{'='*60}")
            print(title)
            print("=" * 60)
        self._log_to_file("INFO", f"=== {title} ===")

    def subsection(self, title):
        """서브섹션 헤더 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"\n[{title}]")
        self._log_to_file("INFO", f"[{title}]")

    def success(self, message):
        """성공 메시지 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"SUCCESS: {message}")
        self._log_to_file("INFO", f"SUCCESS: {message}")

    def warning(self, message):
        """경고 메시지 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"WARNING: {message}")
        self._log_to_file("WARNING", message)

    def summary(self, items):
        """요약 정보 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            for key, value in items.items():
                print(f"  {key}: {value}")
        self._log_to_file("INFO", "=== Summary ===")
        for key, value in items.items():
            self._log_to_file("INFO", f"  {key}: {value}")


# 전역 로거 인스턴스 (conftest에서 초기화)
logger = None


def init_logger(verbosity=1, log_file=None):
    """로거 초기화

    Args:
        verbosity: 로그 레벨 (0: QUIET, 1: NORMAL, 2: VERBOSE)
        log_file: 로그 파일 경로 (선택)
    """
    global logger
    logger = Logger(verbosity, log_file)
    return logger


def get_logger():
    """로거 인스턴스 반환"""
    global logger
    if logger is None:
        logger = Logger(1)  # 기본값
    return logger
