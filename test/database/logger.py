"""
테스트 데이터 생성 로깅 유틸리티
verbosity 레벨에 따라 출력을 제어
"""


class Logger:
    """로깅 유틸리티 클래스"""
    
    # Verbosity 레벨
    QUIET = 0    # 오류만
    NORMAL = 1   # 주요 진행상황
    VERBOSE = 2  # 모든 디버그 정보
    
    def __init__(self, verbosity=1):
        """
        Args:
            verbosity: 로그 레벨 (0: QUIET, 1: NORMAL, 2: VERBOSE)
        """
        self.verbosity = verbosity
    
    def error(self, message):
        """항상 표시되는 오류 메시지"""
        print(f"[ERROR] {message}")
    
    def info(self, message):
        """레벨 1 이상: 주요 정보"""
        if self.verbosity >= self.NORMAL:
            print(message)
    
    def debug(self, message):
        """레벨 2: 상세 디버그 정보"""
        if self.verbosity >= self.VERBOSE:
            print(message)
    
    def section(self, title):
        """섹션 헤더 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"\n{'='*60}")
            print(title)
            print('='*60)
    
    def subsection(self, title):
        """서브섹션 헤더 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"\n[{title}]")
    
    def success(self, message):
        """성공 메시지 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"SUCCESS: {message}")
    
    def warning(self, message):
        """경고 메시지 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            print(f"WARNING: {message}")
    
    def summary(self, items):
        """요약 정보 (레벨 1 이상)"""
        if self.verbosity >= self.NORMAL:
            for key, value in items.items():
                print(f"  {key}: {value}")


# 전역 로거 인스턴스 (conftest에서 초기화)
logger = None


def init_logger(verbosity=1):
    """로거 초기화"""
    global logger
    logger = Logger(verbosity)
    return logger


def get_logger():
    """로거 인스턴스 반환"""
    global logger
    if logger is None:
        logger = Logger(1)  # 기본값
    return logger
