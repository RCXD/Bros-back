"""
HTTP 요청/응답 인터셉터
모든 엔드포인트에 적용되어 에러 응답을 자동으로 로깅
"""

from flask import request, jsonify
from functools import wraps
import logging
import json
from datetime import datetime

# 로거 설정 (성공/실패 분리)
logger = logging.getLogger(__name__)
success_logger = logging.getLogger("success")
error_logger = logging.getLogger("error")


def log_response(response):
    """
    모든 응답을 로깅 (성공/실패 분리)

    Args:
        response: Flask Response 객체
    """
    try:
        # 요청 정보
        request_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": request.url,
            "path": request.path,
            "remote_addr": request.remote_addr,
            "status_code": response.status_code,
        }

        # 요청 헤더 (민감한 정보 제외)
        headers = dict(request.headers)
        if "Authorization" in headers:
            headers["Authorization"] = "Bearer ***"
        request_data["headers"] = headers

        # 요청 바디
        if request.is_json:
            try:
                body = request.get_json()
                # 비밀번호 마스킹
                if isinstance(body, dict):
                    if "password" in body:
                        body["password"] = "***"
                    if "token" in body:
                        body["token"] = "***"
                request_data["request_body"] = body
            except:
                request_data["request_body"] = "Unable to parse JSON"
        elif request.form:
            form_data = dict(request.form)
            if "password" in form_data:
                form_data["password"] = "***"
            request_data["form_data"] = form_data

        # 응답 데이터
        try:
            response_data = response.get_json()
            request_data["response_body"] = response_data
        except:
            response_data_text = response.get_data(as_text=True)
            request_data["response_body"] = (
                response_data_text[:500] if response_data_text else None
            )

        # 로그 레벨에 따라 분리
        if response.status_code >= 500:
            # 500번대 에러는 error.log에만
            error_logger.error(
                f"Server Error Response:\n{json.dumps(request_data, indent=2, ensure_ascii=False)}"
            )
        elif response.status_code >= 400:
            # 400번대 에러는 error.log에만
            error_logger.warning(
                f"Client Error Response:\n{json.dumps(request_data, indent=2, ensure_ascii=False)}"
            )
        else:
            # 200번대 성공은 success.log에만
            success_logger.info(
                f"Success Response:\n{json.dumps(request_data, indent=2, ensure_ascii=False)}"
            )

    except Exception as e:
        error_logger.error(f"Error logging response: {str(e)}")

    return response


def register_interceptors(app):
    """
    Flask 앱에 인터셉터 등록

    Args:
        app: Flask 애플리케이션 인스턴스
    """

    @app.before_request
    def log_request_info():
        """요청 시작 시 로깅 (선택적)"""
        if app.config.get("DEBUG"):
            logger.debug(f"Request: {request.method} {request.path}")

    @app.after_request
    def intercept_response(response):
        """모든 응답을 인터셉트하여 로깅 (성공/실패 분리)"""
        return log_response(response)

    @app.errorhandler(404)
    def handle_404(error):
        """404 에러 핸들러"""
        response = jsonify(
            {"message": "요청하신 리소스를 찾을 수 없습니다", "path": request.path}
        )
        response.status_code = 404
        return response

    @app.errorhandler(500)
    def handle_500(error):
        """500 에러 핸들러"""
        logger.error(f"Internal Server Error: {str(error)}", exc_info=True)
        response = jsonify(
            {
                "message": "서버 내부 오류가 발생했습니다",
                "error": (
                    str(error) if app.config.get("DEBUG") else "Internal Server Error"
                ),
            }
        )
        response.status_code = 500
        return response

    @app.errorhandler(Exception)
    def handle_exception(error):
        """처리되지 않은 예외 핸들러"""
        logger.error(f"Unhandled Exception: {str(error)}", exc_info=True)

        # HTTP 예외인 경우
        if hasattr(error, "code"):
            response = jsonify(
                {
                    "message": getattr(error, "description", str(error)),
                    "error": error.__class__.__name__,
                }
            )
            response.status_code = error.code
        else:
            # 일반 예외
            response = jsonify(
                {
                    "message": "예상치 못한 오류가 발생했습니다",
                    "error": (
                        str(error)
                        if app.config.get("DEBUG")
                        else "Internal Server Error"
                    ),
                }
            )
            response.status_code = 500

        return response

    logger.info("HTTP interceptors registered successfully")


def setup_logging(app):
    """
    로깅 설정

    Args:
        app: Flask 애플리케이션 인스턴스
    """
    import os
    from logging.handlers import RotatingFileHandler

    # 로그 디렉토리 생성 (apps/logs)
    log_dir = os.path.join(app.root_path, "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 로그 포맷
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    # === 에러 로그 파일 핸들러 (error.log - 400/500번대만) ===
    error_log_file = os.path.join(log_dir, "error.log")
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)

    # error 전용 로거 설정
    error_logger = logging.getLogger("error")
    error_logger.addHandler(error_handler)
    error_logger.setLevel(logging.WARNING)
    error_logger.propagate = False  # 상위 로거로 전파 방지

    # === 성공 로그 파일 핸들러 (success.log - 200번대만) ===
    success_log_file = os.path.join(log_dir, "success.log")
    success_handler = RotatingFileHandler(
        success_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding="utf-8",
    )
    success_handler.setLevel(logging.INFO)
    success_handler.setFormatter(formatter)

    # success 전용 로거 설정
    success_logger = logging.getLogger("success")
    success_logger.addHandler(success_handler)
    success_logger.setLevel(logging.INFO)
    success_logger.propagate = False  # 상위 로거로 전파 방지

    # === 앱 로거 설정 (콘솔 출력용) ===
    app.logger.setLevel(logging.INFO)

    # 콘솔 핸들러는 WARNING 이상만 출력
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    app.logger.addHandler(console_handler)

    # === SQLAlchemy 로거 완전 비활성화 (터미널 출력 방지) ===
    # 모든 SQLAlchemy 관련 로거를 CRITICAL로 설정 (사실상 비활성화)
    logging.getLogger("sqlalchemy").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.CRITICAL)

    # SQLAlchemy 로거의 propagate도 비활성화
    for logger_name in [
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "sqlalchemy.orm",
    ]:
        sql_logger = logging.getLogger(logger_name)
        sql_logger.propagate = False
        sql_logger.handlers = []  # 모든 핸들러 제거

    # SQLAlchemy echo 비활성화
    app.config["SQLALCHEMY_ECHO"] = False

    # === Werkzeug 로거 커스터마이징 (IP에 닉네임 추가) ===
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.INFO)

    # IP 닉네임 매핑
    ip_nicknames = app.config.get("IP_NICKNAMES", {})

    # 커스텀 포맷터 클래스
    class IPNicknameFormatter(logging.Formatter):
        def format(self, record):
            # 원본 메시지 가져오기
            original_msg = super().format(record)

            # IP 주소 패턴 찾아서 닉네임 추가
            for ip, nickname in ip_nicknames.items():
                if ip in original_msg:
                    # "192.168.1.89 - -" -> "192.168.1.89(DEV3) - -"
                    original_msg = original_msg.replace(
                        f"{ip} - -", f"{ip}({nickname}) - -"
                    )
                    break

            return original_msg

    # Werkzeug 로거의 모든 핸들러에 커스텀 포맷터 적용
    werkzeug_formatter = IPNicknameFormatter()
    for handler in werkzeug_logger.handlers:
        handler.setFormatter(werkzeug_formatter)

    # 핸들러가 없으면 새로 추가
    if not werkzeug_logger.handlers:
        werkzeug_handler = logging.StreamHandler()
        werkzeug_handler.setFormatter(werkzeug_formatter)
        werkzeug_logger.addHandler(werkzeug_handler)

    logger.info("Logging configured successfully")
