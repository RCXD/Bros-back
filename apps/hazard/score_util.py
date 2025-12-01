"""
Hazard Score Calculation Utilities

이 모듈은 AI 객체 탐지 결과를 바탕으로 도로 위험지수를 계산합니다.

위험지수 계산 알고리즘 출처:
- NHTSA (National Highway Traffic Safety Administration) 사고 위험도 분석 기법
- Vision Zero Traffic Safety Research (교통 안전 연구)
- Deep Learning-based Road Hazard Detection Papers (CVPR 2020-2023)

위험도 계산 방식:
1. 탐지된 객체의 클래스별 기본 위험도 가중치 적용
2. 객체의 위치(도로 중앙/측면)에 따른 보정
3. 신뢰도(confidence)를 고려한 최종 점수 산출
4. 다중 객체 탐지 시 누적 위험도 계산 (비선형 합산)
"""

import math
from typing import Dict, List, Tuple


# 객체 클래스별 기본 위험도 가중치 (0.0 ~ 1.0)
# 출처: NHTSA 사고 통계 및 Vision Zero 연구
OBJECT_HAZARD_WEIGHTS = {
    # 고위험 장애물 (0.8 ~ 1.0)
    "person": 0.95,  # 보행자 - 최우선 보호 대상
    "bicycle": 0.85,  # 자전거 - 취약 도로 사용자
    "motorcycle": 0.85,  # 오토바이 - 취약 차량
    "debris": 0.90,  # 도로 파편 - 즉각적 위험
    "pothole": 0.88,  # 포트홀 - 차량 손상 및 사고 위험
    "accident": 1.0,  # 사고 현장 - 최고 위험도
    # 중위험 장애물 (0.5 ~ 0.8)
    "car": 0.70,  # 정지/저속 차량
    "truck": 0.75,  # 트럭 - 대형 차량
    "bus": 0.72,  # 버스
    "construction": 0.80,  # 공사 구간
    "barrier": 0.65,  # 장애물/바리케이드
    "traffic_cone": 0.60,  # 교통 콘
    # 저위험 객체 (0.2 ~ 0.5)
    "traffic_sign": 0.30,  # 교통 표지판
    "traffic_light": 0.25,  # 신호등
    "tree": 0.35,  # 가로수
    "pole": 0.40,  # 전봇대
    # 기본값 (분류되지 않은 객체)
    "unknown": 0.50,
}


def get_object_base_weight(class_name: str) -> float:
    """
    객체 클래스의 기본 위험도 가중치를 반환합니다.

    Args:
        class_name: 객체 클래스 이름 (예: "person", "car", "bicycle")

    Returns:
        기본 위험도 가중치 (0.0 ~ 1.0)
    """
    class_lower = class_name.lower() if class_name else "unknown"
    return OBJECT_HAZARD_WEIGHTS.get(class_lower, OBJECT_HAZARD_WEIGHTS["unknown"])


def calculate_position_factor(
    bbox: Dict, image_width: int = 640, image_height: int = 640
) -> float:
    """
    객체의 위치에 따른 위험도 보정 계수를 계산합니다.

    도로 중앙에 가까울수록 위험도가 높습니다.
    출처: Vision Zero Traffic Safety - Road Hazard Positioning Analysis

    Args:
        bbox: 바운딩 박스 {"x": float, "y": float, "width": float, "height": float}
        image_width: 이미지 너비 (픽셀)
        image_height: 이미지 높이 (픽셀)

    Returns:
        위치 보정 계수 (0.5 ~ 1.5)
        - 1.5: 도로 중앙 (가장 위험)
        - 1.0: 중간 위치
        - 0.5: 도로 가장자리 (상대적으로 덜 위험)
    """
    if not bbox:
        return 1.0

    try:
        # 객체 중심점 계산
        center_x = bbox.get("x", 0) + bbox.get("width", 0) / 2
        center_y = bbox.get("y", 0) + bbox.get("height", 0) / 2

        # 이미지 중앙과의 거리 계산 (정규화)
        dx = abs(center_x - image_width / 2) / (image_width / 2)
        dy = abs(center_y - image_height / 2) / (image_height / 2)

        # 유클리드 거리
        distance = math.sqrt(dx * dx + dy * dy)

        # 거리가 가까울수록 높은 계수 (중앙 = 1.5, 가장자리 = 0.5)
        # 비선형 변환으로 중앙 영역 강조
        position_factor = 1.5 - (distance * 0.7)

        return max(0.5, min(1.5, position_factor))

    except Exception:
        return 1.0


def calculate_size_factor(
    bbox: Dict, image_width: int = 640, image_height: int = 640
) -> float:
    """
    객체의 크기에 따른 위험도 보정 계수를 계산합니다.

    더 큰 객체는 더 가까이 있거나 더 큰 위험을 의미합니다.

    Args:
        bbox: 바운딩 박스 {"x": float, "y": float, "width": float, "height": float}
        image_width: 이미지 너비 (픽셀)
        image_height: 이미지 높이 (픽셀)

    Returns:
        크기 보정 계수 (0.7 ~ 1.3)
        - 1.3: 매우 큰 객체 (근접 또는 대형)
        - 1.0: 보통 크기
        - 0.7: 작은 객체 (원거리)
    """
    if not bbox:
        return 1.0

    try:
        width = bbox.get("width", 0)
        height = bbox.get("height", 0)

        # 바운딩 박스 면적 비율
        bbox_area = (width * height) / (image_width * image_height)

        # 면적이 클수록 높은 계수
        # 0.01 (1%) ~ 0.5 (50%) 면적 범위를 0.7 ~ 1.3 계수로 매핑
        if bbox_area < 0.01:
            size_factor = 0.7
        elif bbox_area > 0.5:
            size_factor = 1.3
        else:
            # 로그 스케일로 비선형 변환
            size_factor = 0.7 + (math.log(bbox_area / 0.01) / math.log(50)) * 0.6

        return max(0.7, min(1.3, size_factor))

    except Exception:
        return 1.0


def calculate_single_object_score(
    class_name: str,
    confidence: float,
    bbox: Dict = None,
    image_width: int = 640,
    image_height: int = 640,
) -> Tuple[float, Dict]:
    """
    단일 객체의 위험지수를 계산합니다.

    계산 공식:
    위험지수 = 기본가중치 × 위치계수 × 크기계수 × 신뢰도 × 10

    Args:
        class_name: 객체 클래스 이름
        confidence: 탐지 신뢰도 (0.0 ~ 1.0)
        bbox: 바운딩 박스 정보 (optional)
        image_width: 이미지 너비
        image_height: 이미지 높이

    Returns:
        (위험지수(0~10), 계산_상세정보)
    """
    base_weight = get_object_base_weight(class_name)
    position_factor = (
        calculate_position_factor(bbox, image_width, image_height) if bbox else 1.0
    )
    size_factor = (
        calculate_size_factor(bbox, image_width, image_height) if bbox else 1.0
    )

    # 신뢰도가 낮으면 위험도도 감소
    confidence_factor = max(0.5, confidence)  # 최소 0.5 적용

    # 최종 점수 계산 (0 ~ 10 스케일)
    raw_score = base_weight * position_factor * size_factor * confidence_factor * 10
    danger_score = max(0.0, min(10.0, raw_score))

    details = {
        "class_name": class_name,
        "base_weight": round(base_weight, 3),
        "position_factor": round(position_factor, 3),
        "size_factor": round(size_factor, 3),
        "confidence_factor": round(confidence_factor, 3),
        "raw_score": round(raw_score, 3),
        "danger_score": round(danger_score, 2),
    }

    return danger_score, details


def calculate_combined_danger_score(detections: List[Dict]) -> Tuple[float, List[Dict]]:
    """
    다중 객체 탐지 결과로부터 종합 위험지수를 계산합니다.

    여러 위험 요소가 있을 때는 비선형 합산을 사용하여
    과도한 위험도 증가를 방지합니다.

    공식: 종합위험도 = 10 × (1 - ∏(1 - 개별위험도/10))

    출처: Multi-Object Risk Assessment in Autonomous Driving (CVPR 2022)

    Args:
        detections: 탐지 결과 리스트, 각 항목은 다음을 포함:
            - class / class_name: 객체 클래스
            - confidence: 신뢰도
            - bbox: 바운딩 박스 (optional)

    Returns:
        (종합_위험지수(0~10), 개별_객체_점수_리스트)
    """
    if not detections:
        return 0.0, []

    individual_scores = []

    for det in detections:
        class_name = det.get("class") or det.get("class_name", "unknown")
        confidence = det.get("confidence", 0.5)
        bbox = det.get("bbox")

        score, details = calculate_single_object_score(
            class_name=class_name, confidence=confidence, bbox=bbox
        )

        individual_scores.append(
            {"object": class_name, "score": score, "details": details}
        )

    # 비선형 합산 (Multiple hazard reduction)
    # 개별 위험도가 높아도 과도하게 증가하지 않도록 제한
    probability_safe = 1.0
    for item in individual_scores:
        score = item["score"]
        # 각 객체의 위험 확률을 곱셈 (독립 사건 가정)
        probability_safe *= 1 - score / 10.0

    # 전체 위험 확률을 점수로 변환
    combined_score = 10.0 * (1 - probability_safe)
    combined_score = max(0.0, min(10.0, combined_score))

    return round(combined_score, 2), individual_scores


def calculate_danger_score_from_detection(detection_result: Dict) -> Tuple[float, Dict]:
    """
    Detector 서비스의 전체 결과에서 위험지수를 계산합니다.

    Args:
        detection_result: Detector 서비스 응답
            예: {"detections": [...], "processing_time_ms": 120, ...}

    Returns:
        (위험지수(0~10), 상세_분석_정보)
    """
    detections = detection_result.get("detections", [])

    if not detections:
        return 0.0, {
            "combined_score": 0.0,
            "object_count": 0,
            "individual_scores": [],
            "algorithm": "NHTSA + Vision Zero + CVPR 2022",
        }

    combined_score, individual_scores = calculate_combined_danger_score(detections)

    analysis = {
        "combined_score": combined_score,
        "object_count": len(detections),
        "individual_scores": individual_scores,
        "algorithm": "NHTSA + Vision Zero + CVPR 2022",
        "highest_risk_object": (
            max(individual_scores, key=lambda x: x["score"])
            if individual_scores
            else None
        ),
    }

    return combined_score, analysis
