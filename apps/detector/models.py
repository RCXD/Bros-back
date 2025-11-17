"""
Detection Models - AI object detection and semantic segmentation results storage

Server Configuration:
- Port 8888 (Required): Semantic object detection server
  Handles: Object detection, semantic segmentation
  
- Port 8889 (Optional): Road segmentation server
  Handles: Road boundary detection, lane detection
  Can be skipped if malfunctioning - system will continue working
"""
from datetime import datetime
from sqlalchemy import Enum as SQLEnum
import enum


class DetectionType(enum.Enum):
    """Types of AI detection operations"""
    OBJECT_DETECTION = "object_detection"
    SEMANTIC_SEGMENTATION = "semantic_segmentation"
    ROAD_BOUNDARY = "road_boundary"
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"


class DetectionStatus(enum.Enum):
    """Status of detection processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def init_models(db):
    """Initialize detection models with db instance"""
    
    class Detection(db.Model):
        """
        Main detection record - stores metadata about AI detection requests
        """
        __tablename__ = "detections"
        
        detection_id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
        detection_type = db.Column(SQLEnum(DetectionType), nullable=False)
        status = db.Column(SQLEnum(DetectionStatus), default=DetectionStatus.PENDING)
        
        # Image information
        image_path = db.Column(db.String(500))  # Path to original image
        image_url = db.Column(db.String(500))   # Public URL if applicable
        
        # AI Server information
        ai_server = db.Column(db.String(50))    # e.g., "192.168.1.79:8888"
        model_name = db.Column(db.String(100))  # e.g., "YOLOv8", "DeepLabV3"
        model_version = db.Column(db.String(50))
        
        # Processing metrics
        confidence_threshold = db.Column(db.Float, default=0.5)
        processing_time_ms = db.Column(db.Integer)  # Processing duration
        
        # Result summary
        result_summary = db.Column(db.JSON)  # Quick overview of results
        error_message = db.Column(db.Text)   # Error details if failed
        
        # Timestamps
        created_at = db.Column(db.DateTime, default=datetime.now)
        completed_at = db.Column(db.DateTime)
        
        # Relationships
        objects = db.relationship("DetectedObject", backref="detection", lazy=True, cascade="all, delete-orphan")
        segments = db.relationship("SemanticSegment", backref="detection", lazy=True, cascade="all, delete-orphan")
        
        def to_dict(self):
            """Convert to dictionary for JSON response"""
            return {
                "detection_id": self.detection_id,
                "user_id": self.user_id,
                "detection_type": self.detection_type.value if self.detection_type else None,
                "status": self.status.value if self.status else None,
                "image_path": self.image_path,
                "image_url": self.image_url,
                "ai_server": self.ai_server,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "confidence_threshold": self.confidence_threshold,
                "processing_time_ms": self.processing_time_ms,
                "result_summary": self.result_summary,
                "error_message": self.error_message,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            }
    
    
    class DetectedObject(db.Model):
        """
        Individual objects detected in an image
        Stores bounding boxes, labels, and confidence scores
        """
        __tablename__ = "detected_objects"
        
        object_id = db.Column(db.Integer, primary_key=True)
        detection_id = db.Column(db.Integer, db.ForeignKey("detections.detection_id"), nullable=False)
        
        # Object classification
        class_name = db.Column(db.String(100), nullable=False)  # e.g., "car", "person", "bicycle"
        class_id = db.Column(db.Integer)
        confidence = db.Column(db.Float, nullable=False)  # 0.0 to 1.0
        
        # Bounding box coordinates (normalized or pixel values)
        bbox_x = db.Column(db.Float, nullable=False)  # Top-left x
        bbox_y = db.Column(db.Float, nullable=False)  # Top-left y
        bbox_width = db.Column(db.Float, nullable=False)
        bbox_height = db.Column(db.Float, nullable=False)
        
        # Additional attributes
        attributes = db.Column(db.JSON)  # Store additional properties like color, state, etc.
        
        # Tracking (for video/sequence analysis)
        track_id = db.Column(db.Integer)  # If tracking across frames
        
        created_at = db.Column(db.DateTime, default=datetime.now)
        
        def to_dict(self):
            """Convert to dictionary for JSON response"""
            return {
                "object_id": self.object_id,
                "detection_id": self.detection_id,
                "class_name": self.class_name,
                "class_id": self.class_id,
                "confidence": self.confidence,
                "bbox": {
                    "x": self.bbox_x,
                    "y": self.bbox_y,
                    "width": self.bbox_width,
                    "height": self.bbox_height
                },
                "attributes": self.attributes,
                "track_id": self.track_id,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }
    
    
    class SemanticSegment(db.Model):
        """
        Semantic segmentation results
        Stores pixel-level classification data from segmentation models
        """
        __tablename__ = "semantic_segments"
        
        segment_id = db.Column(db.Integer, primary_key=True)
        detection_id = db.Column(db.Integer, db.ForeignKey("detections.detection_id"), nullable=False)
        
        # Segment classification
        class_name = db.Column(db.String(100), nullable=False)  # e.g., "road", "sidewalk", "building"
        class_id = db.Column(db.Integer)
        color_code = db.Column(db.String(20))  # RGB or hex color for visualization
        
        # Segment metrics
        pixel_count = db.Column(db.Integer)  # Number of pixels in this segment
        percentage = db.Column(db.Float)     # Percentage of image
        confidence = db.Column(db.Float)     # Average confidence for this segment
        
        # Mask data (for precise boundaries)
        mask_path = db.Column(db.String(500))  # Path to binary mask file
        mask_data = db.Column(db.LargeBinary)  # Or store compressed mask directly
        polygon_data = db.Column(db.JSON)      # Polygon coordinates if available
        
        # Region properties
        centroid_x = db.Column(db.Float)  # Center of mass x
        centroid_y = db.Column(db.Float)  # Center of mass y
        area = db.Column(db.Float)        # Area in pixels or normalized
        
        created_at = db.Column(db.DateTime, default=datetime.now)
        
        def to_dict(self):
            """Convert to dictionary for JSON response"""
            return {
                "segment_id": self.segment_id,
                "detection_id": self.detection_id,
                "class_name": self.class_name,
                "class_id": self.class_id,
                "color_code": self.color_code,
                "pixel_count": self.pixel_count,
                "percentage": self.percentage,
                "confidence": self.confidence,
                "mask_path": self.mask_path,
                "polygon_data": self.polygon_data,
                "centroid": {
                    "x": self.centroid_x,
                    "y": self.centroid_y
                },
                "area": self.area,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }
    
    
    class DetectionAnnotation(db.Model):
        """
        User annotations/corrections on detection results
        Useful for improving model accuracy and creating training data
        """
        __tablename__ = "detection_annotations"
        
        annotation_id = db.Column(db.Integer, primary_key=True)
        detection_id = db.Column(db.Integer, db.ForeignKey("detections.detection_id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
        
        # Reference to corrected object/segment
        object_id = db.Column(db.Integer, db.ForeignKey("detected_objects.object_id"))
        segment_id = db.Column(db.Integer, db.ForeignKey("semantic_segments.segment_id"))
        
        # Annotation details
        annotation_type = db.Column(db.String(50))  # "correction", "false_positive", "false_negative"
        corrected_class = db.Column(db.String(100))
        comments = db.Column(db.Text)
        
        # Corrected bounding box (if applicable)
        corrected_bbox = db.Column(db.JSON)
        
        is_verified = db.Column(db.Boolean, default=False)
        created_at = db.Column(db.DateTime, default=datetime.now)
        
        def to_dict(self):
            """Convert to dictionary for JSON response"""
            return {
                "annotation_id": self.annotation_id,
                "detection_id": self.detection_id,
                "user_id": self.user_id,
                "object_id": self.object_id,
                "segment_id": self.segment_id,
                "annotation_type": self.annotation_type,
                "corrected_class": self.corrected_class,
                "comments": self.comments,
                "corrected_bbox": self.corrected_bbox,
                "is_verified": self.is_verified,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }
    
    
    return Detection, DetectedObject, SemanticSegment, DetectionAnnotation
