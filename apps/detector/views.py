# """
# Detector module - AI object detection and analysis
# """
# from flask import Blueprint, jsonify, request, current_app
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from datetime import datetime
# import os

# from .models import DetectionType, DetectionStatus, init_models
# from .detection_utils import (
#     get_ai_server_client,
#     DetectionResultProcessor,
#     validate_image
# )
# from ..common.image_handlers import save_uploaded_image

# bp = Blueprint("detector", __name__)

# # Initialize models (will be set up when app context is available)
# Detection = None
# DetectedObject = None
# SemanticSegment = None
# DetectionAnnotation = None


# def init_detector_models(db):
#     """Initialize detector models with db instance"""
#     global Detection, DetectedObject, SemanticSegment, DetectionAnnotation
#     Detection, DetectedObject, SemanticSegment, DetectionAnnotation = init_models(db)


# @bp.post("/objects")
# @jwt_required()
# def detect_objects():
#     """
#     Detect objects in uploaded image using semantic object detection server (8888)
#     Form data:
#         - image: Required (multipart file)
#         - confidence: Optional (threshold 0-1, default 0.5)
#     """
#     if "image" not in request.files:
#         return jsonify({"message": "Image file is required"}), 400
    
#     image_file = request.files["image"]
#     image_data = image_file.read()
    
#     # Validate image
#     is_valid, error_msg = validate_image(image_data)
#     if not is_valid:
#         return jsonify({"message": error_msg}), 400
    
#     # Get parameters
#     confidence = float(request.form.get("confidence", 0.5))
#     user_id = get_jwt_identity()
    
#     # Save image
#     try:
#         image_path = save_uploaded_image(image_file, folder="detections")
#     except Exception as e:
#         return jsonify({"message": f"Failed to save image: {str(e)}"}), 500
    
#     # Create detection record
#     from ..config.common import db
#     detection = Detection(
#         user_id=user_id,
#         detection_type=DetectionType.OBJECT_DETECTION,
#         status=DetectionStatus.PROCESSING,
#         image_path=image_path,
#         confidence_threshold=confidence
#     )
#     db.session.add(detection)
#     db.session.commit()
    
#     # Call AI server (semantic object detection on 8888)
#     try:
#         ai_client = get_ai_server_client("object")
#         detection.ai_server = ai_client.server_url
        
#         result = ai_client.detect_objects(image_data, confidence)
        
#         if 'error' in result:
#             detection.status = DetectionStatus.FAILED
#             detection.error_message = result['error']
#             db.session.commit()
#             return jsonify({
#                 "detection_id": detection.detection_id,
#                 "status": "failed",
#                 "message": result['error']
#             }), 500
        
#         # Process results
#         processor = DetectionResultProcessor()
#         objects_list, summary = processor.process_yolo_results(result)
        
#         # Save detected objects
#         for obj_data in objects_list:
#             obj = DetectedObject(
#                 detection_id=detection.detection_id,
#                 **obj_data
#             )
#             db.session.add(obj)
        
#         # Update detection record
#         detection.status = DetectionStatus.COMPLETED
#         detection.completed_at = datetime.now()
#         detection.processing_time_ms = result.get('processing_time_ms')
#         detection.result_summary = summary
#         detection.model_name = result.get('model_info', {}).get('name', 'YOLO')
#         detection.model_version = result.get('model_info', {}).get('version')
        
#         db.session.commit()
        
#         return jsonify({
#             "detection_id": detection.detection_id,
#             "status": "completed",
#             "objects": [obj.to_dict() for obj in detection.objects],
#             "summary": summary,
#             "processing_time_ms": detection.processing_time_ms
#         }), 200
        
#     except Exception as e:
#         detection.status = DetectionStatus.FAILED
#         detection.error_message = str(e)
#         db.session.commit()
#         return jsonify({
#             "detection_id": detection.detection_id,
#             "status": "failed",
#             "message": str(e)
#         }), 500



# @bp.post("/semantic")
# @jwt_required()
# def semantic_segmentation():
#     """
#     Perform semantic segmentation on image using semantic object detection server (8888)
#     Form data:
#         - image: Required (multipart file)
#         - model: Optional (model variant to use, default "default")
#     """
#     if "image" not in request.files:
#         return jsonify({"message": "Image file is required"}), 400
    
#     image_file = request.files["image"]
#     image_data = image_file.read()
    
#     # Validate image
#     is_valid, error_msg = validate_image(image_data)
#     if not is_valid:
#         return jsonify({"message": error_msg}), 400
    
#     # Get parameters
#     model = request.form.get("model", "default")
#     user_id = get_jwt_identity()
    
#     # Save image
#     try:
#         image_path = save_uploaded_image(image_file, folder="detections")
#     except Exception as e:
#         return jsonify({"message": f"Failed to save image: {str(e)}"}), 500
    
#     # Create detection record
#     from ..config.common import db
#     detection = Detection(
#         user_id=user_id,
#         detection_type=DetectionType.SEMANTIC_SEGMENTATION,
#         status=DetectionStatus.PROCESSING,
#         image_path=image_path
#     )
#     db.session.add(detection)
#     db.session.commit()
    
#     # Call AI server (semantic object detection on 8888)
#     try:
#         ai_client = get_ai_server_client("object")
#         detection.ai_server = ai_client.server_url
        
#         result = ai_client.semantic_segmentation(image_data, model)
        
#         if 'error' in result:
#             detection.status = DetectionStatus.FAILED
#             detection.error_message = result['error']
#             db.session.commit()
#             return jsonify({
#                 "detection_id": detection.detection_id,
#                 "status": "failed",
#                 "message": result['error']
#             }), 500
        
#         # Process results
#         processor = DetectionResultProcessor()
#         segments_list, summary = processor.process_segmentation_results(result)
        
#         # Save segments
#         for seg_data in segments_list:
#             segment = SemanticSegment(
#                 detection_id=detection.detection_id,
#                 **seg_data
#             )
#             db.session.add(segment)
        
#         # Update detection record
#         detection.status = DetectionStatus.COMPLETED
#         detection.completed_at = datetime.now()
#         detection.processing_time_ms = result.get('processing_time_ms')
#         detection.result_summary = summary
#         detection.model_name = model
        
#         db.session.commit()
        
#         return jsonify({
#             "detection_id": detection.detection_id,
#             "status": "completed",
#             "segments": [seg.to_dict() for seg in detection.segments],
#             "summary": summary,
#             "processing_time_ms": detection.processing_time_ms
#         }), 200
        
#     except Exception as e:
#         detection.status = DetectionStatus.FAILED
#         detection.error_message = str(e)
#         db.session.commit()
#         return jsonify({
#             "detection_id": detection.detection_id,
#             "status": "failed",
#             "message": str(e)
#         }), 500


# @bp.post("/road-boundary")
# @jwt_required()
# def detect_road_boundary():
#     """
#     Detect road boundaries in image using road segmentation server (8889)
#     Note: This endpoint is optional and will gracefully fail if 8889 is unavailable
#     Form data:
#         - image: Required (multipart file)
#     """
#     if "image" not in request.files:
#         return jsonify({"message": "Image file is required"}), 400
    
#     image_file = request.files["image"]
#     image_data = image_file.read()
    
#     # Validate image
#     is_valid, error_msg = validate_image(image_data)
#     if not is_valid:
#         return jsonify({"message": error_msg}), 400
    
#     user_id = get_jwt_identity()
    
#     # Save image
#     try:
#         image_path = save_uploaded_image(image_file, folder="detections")
#     except Exception as e:
#         return jsonify({"message": f"Failed to save image: {str(e)}"}), 500
    
#     # Create detection record
#     from ..config.common import db
#     detection = Detection(
#         user_id=user_id,
#         detection_type=DetectionType.ROAD_BOUNDARY,
#         status=DetectionStatus.PROCESSING,
#         image_path=image_path
#     )
#     db.session.add(detection)
#     db.session.commit()
    
#     # Call AI server (road segmentation on 8889 - optional)
#     try:
#         ai_client = get_ai_server_client("road")
#         detection.ai_server = ai_client.server_url
        
#         # Check if road server is available
#         if not ai_client.health_check():
#             detection.status = DetectionStatus.FAILED
#             detection.error_message = "Road segmentation server (8889) is currently unavailable"
#             db.session.commit()
#             return jsonify({
#                 "detection_id": detection.detection_id,
#                 "status": "failed",
#                 "message": "Road segmentation server is currently unavailable",
#                 "note": "Server 8889 can be skipped when malfunctioning"
#             }), 503
        
#         result = ai_client.detect_road_boundary(image_data)
        
#         if 'error' in result:
#             detection.status = DetectionStatus.FAILED
#             detection.error_message = result['error']
#             db.session.commit()
#             return jsonify({
#                 "detection_id": detection.detection_id,
#                 "status": "failed",
#                 "message": result['error']
#             }), 500
        
#         # Update detection record
#         detection.status = DetectionStatus.COMPLETED
#         detection.completed_at = datetime.now()
#         detection.processing_time_ms = result.get('processing_time_ms')
#         detection.result_summary = result
        
#         db.session.commit()
        
#         return jsonify({
#             "detection_id": detection.detection_id,
#             "status": "completed",
#             "result": result,
#             "processing_time_ms": detection.processing_time_ms
#         }), 200
        
#     except Exception as e:
#         detection.status = DetectionStatus.FAILED
#         detection.error_message = str(e)
#         db.session.commit()
#         return jsonify({
#             "detection_id": detection.detection_id,
#             "status": "failed",
#             "message": str(e)
#         }), 500


# @bp.get("/detection/<int:detection_id>")
# @jwt_required()
# def get_detection(detection_id):
#     """
#     Get detection results by ID
#     """
#     user_id = get_jwt_identity()
    
#     from ..config.common import db
#     detection = db.session.get(Detection, detection_id)
    
#     if not detection:
#         return jsonify({"message": "Detection not found"}), 404
    
#     if detection.user_id != user_id:
#         return jsonify({"message": "Unauthorized"}), 403
    
#     response = detection.to_dict()
#     response['objects'] = [obj.to_dict() for obj in detection.objects]
#     response['segments'] = [seg.to_dict() for seg in detection.segments]
    
#     return jsonify(response), 200


# @bp.get("/detections")
# @jwt_required()
# def get_user_detections():
#     """
#     Get all detections for current user
#     Query params:
#         - type: Filter by detection type
#         - status: Filter by status
#         - limit: Max results (default 50)
#         - offset: Pagination offset (default 0)
#     """
#     user_id = get_jwt_identity()
    
#     from ..config.common import db
#     query = Detection.query.filter_by(user_id=user_id)
    
#     # Apply filters
#     detection_type = request.args.get('type')
#     if detection_type:
#         try:
#             query = query.filter_by(detection_type=DetectionType[detection_type.upper()])
#         except KeyError:
#             return jsonify({"message": "Invalid detection type"}), 400
    
#     status = request.args.get('status')
#     if status:
#         try:
#             query = query.filter_by(status=DetectionStatus[status.upper()])
#         except KeyError:
#             return jsonify({"message": "Invalid status"}), 400
    
#     # Pagination
#     limit = min(int(request.args.get('limit', 50)), 100)
#     offset = int(request.args.get('offset', 0))
    
#     query = query.order_by(Detection.created_at.desc())
#     total = query.count()
#     detections = query.limit(limit).offset(offset).all()
    
#     return jsonify({
#         "total": total,
#         "limit": limit,
#         "offset": offset,
#         "detections": [d.to_dict() for d in detections]
#     }), 200


# @bp.get("/models")
# def get_available_models():
#     """Get list of available AI models and their capabilities"""
#     models = []
    
#     # Check semantic object detection server (8888 - primary)
#     try:
#         client = get_ai_server_client("object")
#         if client.health_check():
#             models.append({
#                 "server": client.server_url,
#                 "port": "8888",
#                 "type": "semantic_object_detection",
#                 "status": "online",
#                 "required": True,
#                 "capabilities": [
#                     "object_detection",
#                     "semantic_segmentation"
#                 ]
#             })
#         else:
#             models.append({
#                 "server": client.server_url,
#                 "port": "8888",
#                 "type": "semantic_object_detection",
#                 "status": "offline",
#                 "required": True
#             })
#     except Exception as e:
#         models.append({
#             "server": "http://192.168.1.79:8888",
#             "port": "8888",
#             "type": "semantic_object_detection",
#             "status": "message",
#             "required": True,
#             "message": str(e)
#         })
    
#     # Check road segmentation server (8889 - optional)
#     try:
#         client = get_ai_server_client("road")
#         if client.health_check():
#             models.append({
#                 "server": client.server_url,
#                 "port": "8889",
#                 "type": "road_segmentation",
#                 "status": "online",
#                 "required": False,
#                 "note": "Optional - can be skipped if malfunctioning",
#                 "capabilities": [
#                     "road_boundary_detection",
#                     "lane_detection"
#                 ]
#             })
#         else:
#             models.append({
#                 "server": client.server_url,
#                 "port": "8889",
#                 "type": "road_segmentation",
#                 "status": "offline",
#                 "required": False,
#                 "note": "Optional - can be skipped if malfunctioning"
#             })
#     except Exception as e:
#         models.append({
#             "server": "http://192.168.1.79:8889",
#             "port": "8889",
#             "type": "road_segmentation",
#             "status": "message",
#             "required": False,
#             "note": "Optional - can be skipped if malfunctioning",
#             "message": str(e)
#         })
    
#     return jsonify({"models": models}), 200

