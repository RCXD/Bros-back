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
    """Log every HTTP response to the appropriate log file.

    Successful responses (2xx) are written to ``success.log`` and
    error responses (4xx/5xx) to ``error.log``.  Sensitive headers and
    body fields (``Authorization``, ``password``, ``token``) are masked
    before logging.

    Args:
        response: The :class:`flask.Response` object being returned to
            the client.

    Returns:
        The unmodified *response* object.
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


def register_interceptors(app) -> None:
    """Register before/after request hooks and error handlers on *app*.

    Hooks registered:

    * ``before_request`` – logs the incoming method and path in debug
      mode.
    * ``after_request`` – passes the response through
      :func:`log_response`.
    * ``errorhandler(404)`` – returns a JSON 404 body.
    * ``errorhandler(500)`` – logs the exception and returns a JSON 500
      body.
    * ``errorhandler(Exception)`` – catch-all for unhandled exceptions.

    Args:
        app: The :class:`flask.Flask` application instance to register
            interceptors on.
    """

    @app.before_request
    def log_request_info():
        """Log the incoming request method and path when debug mode is active."""
        if app.config.get("DEBUG"):
            logger.debug(f"Request: {request.method} {request.path}")

    @app.after_request
    def intercept_response(response):
        """Pass every response through the response logger.

        Args:
            response: The :class:`flask.Response` to log.

        Returns:
            The unmodified *response* object.
        """
        return log_response(response)

    @app.errorhandler(404)
    def handle_404(error):
        """Return a JSON 404 response for missing resources."""
        response = jsonify(
            {"message": "요청하신 리소스를 찾을 수 없습니다", "path": request.path}
        )
        response.status_code = 404
        return response

    @app.errorhandler(500)
    def handle_500(error):
        """Log the error and return a JSON 500 response."""
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
        """Catch-all handler for unhandled exceptions.

        HTTP exceptions are returned with their own status code; all
        other exceptions produce a 500 response.
        """
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


def setup_logging(app) -> None:
    """Configure file and stream logging handlers for the Flask app.

    Sets up three rotating file handlers:

    * ``logs/success.log`` – INFO level, for successful responses.
    * ``logs/error.log`` – ERROR level, for error responses and
      exceptions.
    * ``logs/debug.log`` – DEBUG level, all messages.

    A stream handler is also added for console output.  Werkzeug's
    default logger is reconfigured with a custom
    :class:`IPNicknameFormatter` that includes the caller's IP address
    and nickname.

    Args:
        app: The :class:`flask.Flask` application instance to configure
            logging for.
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
        maxBytes=50 * 1024 * 1024,  # 50MB (Windows 롤오버 문제 완화)
        backupCount=5,
        encoding="utf-8",
        delay=True,  # 파일 열기 지연 (잠금 문제 완화)
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
        maxBytes=50 * 1024 * 1024,  # 50MB (Windows 롤오버 문제 완화)
        backupCount=5,
        encoding="utf-8",
        delay=True,  # 파일 열기 지연 (잠금 문제 완화)
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

    class IPNicknameFormatter(logging.Formatter):
        """Custom log formatter that appends a nickname to IP addresses.

        IP-to-nickname mappings are read from the ``IP_NICKNAMES`` Flask
        config key (a ``{ip_str: nickname}`` dict).  For example, the
        log line ``192.168.1.89 - -`` becomes ``192.168.1.89(DEV3) - -``.
        """

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
