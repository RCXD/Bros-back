"""
HTTP 요청/응답 인터셉터
모든 엔드포인트에 적용되어 에러 응답을 자동으로 로깅
"""

from flask import request, jsonify
from functools import wraps
import logging
import json
from datetime import datetime

# 로거 설정
logger = logging.getLogger(__name__)


def log_error_response(response):
    """
    에러 응답(4xx, 5xx)을 로깅

    Args:
        response: Flask Response 객체
    """
    if response.status_code >= 400:
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
                request_data["response_body"] = response.get_data(as_text=True)[:500]

            # 로그 레벨 결정
            if response.status_code >= 500:
                logger.error(
                    f"Server Error Response:\n{json.dumps(request_data, indent=2, ensure_ascii=False)}"
                )
            else:
                logger.warning(
                    f"Client Error Response:\n{json.dumps(request_data, indent=2, ensure_ascii=False)}"
                )

        except Exception as e:
            logger.error(f"Error logging response: {str(e)}")

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
        """모든 응답을 인터셉트하여 에러 응답 로깅"""
        return log_error_response(response)

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

    # 에러 로그 파일 핸들러 (UTF-8 인코딩)
    error_log_file = os.path.join(log_dir, "error.log")
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding="utf-8",  # UTF-8 인코딩 명시
    )
    error_handler.setLevel(logging.WARNING)

    # 성공 로그 파일 핸들러 (UTF-8 인코딩)
    success_log_file = os.path.join(log_dir, "success.log")
    success_handler = RotatingFileHandler(
        success_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding="utf-8",  # UTF-8 인코딩 명시
    )
    success_handler.setLevel(logging.INFO)

    # 로그 포맷
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    error_handler.setFormatter(formatter)
    success_handler.setFormatter(formatter)

    # 앱 로거에 핸들러 추가
    app.logger.addHandler(error_handler)
    app.logger.addHandler(success_handler)
    app.logger.setLevel(logging.INFO)

    # 모듈 로거에도 핸들러 추가
    logger.addHandler(error_handler)
    logger.addHandler(success_handler)
    logger.setLevel(logging.INFO)

    # SQLAlchemy 로거 비활성화 (콘솔 출력 방지)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    logger.info("Logging configured successfully")
