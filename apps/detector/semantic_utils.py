"""
Semantic segmentation utilities - Advanced processing for segmentation results
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path


class SemanticSegmentationProcessor:
    """Advanced processing utilities for semantic segmentation"""
    
    # Common segmentation class mappings
    CITYSCAPES_CLASSES = {
        0: "road", 1: "sidewalk", 2: "building", 3: "wall", 4: "fence",
        5: "pole", 6: "traffic_light", 7: "traffic_sign", 8: "vegetation",
        9: "terrain", 10: "sky", 11: "person", 12: "rider", 13: "car",
        14: "truck", 15: "bus", 16: "train", 17: "motorcycle", 18: "bicycle"
    }
    
    CITYSCAPES_COLORS = {
        0: "#804080", 1: "#f423e8", 2: "#464646", 3: "#6432c8",
        4: "#be9678", 5: "#999999", 6: "#faaa1e", 7: "#dcdc00",
        8: "#6b8e23", 9: "#98fb98", 10: "#87ceeb", 11: "#dc143c",
        12: "#ff0000", 13: "#0000e6", 14: "#1e1e46", 15: "#b4641e",
        16: "#5a5032", 17: "#0000e6", 18: "#770b20"
    }
    
    @staticmethod
    def calculate_segment_statistics(mask: np.ndarray, class_id: int) -> Dict:
        """
        Calculate statistics for a specific segment class
        
        Args:
            mask: Segmentation mask (H x W) with class IDs
            class_id: Class ID to analyze
            
        Returns:
            Statistics dictionary
        """
        class_mask = (mask == class_id).astype(np.uint8)
        pixel_count = np.sum(class_mask)
        total_pixels = mask.size
        
        if pixel_count == 0:
            return None
        
        # Find centroid
        y_coords, x_coords = np.where(class_mask == 1)
        centroid_x = np.mean(x_coords) if len(x_coords) > 0 else 0
        centroid_y = np.mean(y_coords) if len(y_coords) > 0 else 0
        
        return {
            'pixel_count': int(pixel_count),
            'percentage': float(pixel_count / total_pixels * 100),
            'centroid_x': float(centroid_x),
            'centroid_y': float(centroid_y),
            'bounding_box': {
                'min_x': int(np.min(x_coords)) if len(x_coords) > 0 else 0,
                'max_x': int(np.max(x_coords)) if len(x_coords) > 0 else 0,
                'min_y': int(np.min(y_coords)) if len(y_coords) > 0 else 0,
                'max_y': int(np.max(y_coords)) if len(y_coords) > 0 else 0,
            }
        }
    
    @staticmethod
    def extract_road_features(mask: np.ndarray, road_class_ids: List[int] = [0, 1]) -> Dict:
        """
        Extract road-specific features from segmentation mask
        
        Args:
            mask: Segmentation mask
            road_class_ids: List of class IDs representing road surfaces
            
        Returns:
            Road features dictionary
        """
        road_mask = np.isin(mask, road_class_ids).astype(np.uint8)
        
        if np.sum(road_mask) == 0:
            return {'road_detected': False}
        
        # Calculate road coverage
        road_pixels = np.sum(road_mask)
        total_pixels = mask.size
        coverage = road_pixels / total_pixels * 100
        
        # Analyze road position (typically bottom half of image)
        h, w = mask.shape
        bottom_half = road_mask[h//2:, :]
        bottom_coverage = np.sum(bottom_half) / bottom_half.size * 100
        
        # Find road boundaries
        road_columns = np.any(road_mask, axis=0)
        road_left = np.argmax(road_columns)
        road_right = len(road_columns) - np.argmax(road_columns[::-1]) - 1
        road_width_pixels = road_right - road_left
        
        return {
            'road_detected': True,
            'coverage_percentage': float(coverage),
            'bottom_half_coverage': float(bottom_coverage),
            'road_width_pixels': int(road_width_pixels),
            'road_width_percentage': float(road_width_pixels / w * 100),
            'left_boundary': int(road_left),
            'right_boundary': int(road_right),
            'is_road_centered': abs((road_left + road_right) / 2 - w / 2) < w * 0.1
        }
    
    @staticmethod
    def detect_obstacles(mask: np.ndarray, obstacle_classes: List[int] = [11, 12, 13, 14, 15]) -> List[Dict]:
        """
        Detect obstacles in the scene (people, vehicles, etc.)
        
        Args:
            mask: Segmentation mask
            obstacle_classes: Class IDs representing obstacles
            
        Returns:
            List of obstacle dictionaries
        """
        obstacles = []
        
        for class_id in obstacle_classes:
            stats = SemanticSegmentationProcessor.calculate_segment_statistics(mask, class_id)
            if stats and stats['pixel_count'] > 100:  # Minimum size threshold
                obstacle = {
                    'class_id': class_id,
                    'class_name': SemanticSegmentationProcessor.CITYSCAPES_CLASSES.get(class_id, f"class_{class_id}"),
                    **stats
                }
                obstacles.append(obstacle)
        
        # Sort by size (largest first)
        obstacles.sort(key=lambda x: x['pixel_count'], reverse=True)
        
        return obstacles
    
    @staticmethod
    def analyze_scene_composition(mask: np.ndarray) -> Dict:
        """
        Analyze overall scene composition
        
        Args:
            mask: Segmentation mask
            
        Returns:
            Scene composition analysis
        """
        unique_classes, counts = np.unique(mask, return_counts=True)
        total_pixels = mask.size
        
        composition = {}
        for class_id, count in zip(unique_classes, counts):
            class_name = SemanticSegmentationProcessor.CITYSCAPES_CLASSES.get(int(class_id), f"class_{class_id}")
            composition[class_name] = {
                'class_id': int(class_id),
                'pixel_count': int(count),
                'percentage': float(count / total_pixels * 100)
            }
        
        # Categorize scene type
        scene_type = "unknown"
        if composition.get('road', {}).get('percentage', 0) > 30:
            scene_type = "street_view"
        elif composition.get('building', {}).get('percentage', 0) > 40:
            scene_type = "urban"
        elif composition.get('vegetation', {}).get('percentage', 0) > 40:
            scene_type = "nature"
        elif composition.get('sky', {}).get('percentage', 0) > 50:
            scene_type = "outdoor_open"
        
        return {
            'scene_type': scene_type,
            'num_classes': len(unique_classes),
            'composition': composition,
            'dominant_class': max(composition.items(), key=lambda x: x[1]['percentage'])[0]
        }
    
    @staticmethod
    def extract_navigation_info(mask: np.ndarray) -> Dict:
        """
        Extract navigation-relevant information from segmentation
        
        Args:
            mask: Segmentation mask
            
        Returns:
            Navigation information dictionary
        """
        h, w = mask.shape
        
        # Analyze bottom third (driving area)
        driving_area = mask[2*h//3:, :]
        
        # Check for clear path
        road_in_view = np.isin(driving_area, [0, 1])  # road + sidewalk
        clear_path_percentage = np.sum(road_in_view) / driving_area.size * 100
        
        # Detect lane boundaries
        middle_row = driving_area[driving_area.shape[0]//2, :]
        is_road = np.isin(middle_row, [0, 1])
        
        # Find lane edges
        lane_changes = np.diff(is_road.astype(int))
        left_edges = np.where(lane_changes == 1)[0]
        right_edges = np.where(lane_changes == -1)[0]
        
        return {
            'clear_path_percentage': float(clear_path_percentage),
            'path_status': 'clear' if clear_path_percentage > 60 else 'obstructed',
            'num_lane_markings': len(left_edges) + len(right_edges),
            'drivable_area_detected': clear_path_percentage > 30
        }
    
    @staticmethod
    def save_visualization_config(segments: List[Dict], output_path: str) -> None:
        """
        Save visualization configuration for frontend rendering
        
        Args:
            segments: List of segment dictionaries
            output_path: Path to save JSON config
        """
        viz_config = {
            'segments': [],
            'legend': []
        }
        
        for segment in segments:
            viz_config['segments'].append({
                'class_name': segment['class_name'],
                'color': segment.get('color_code', '#000000'),
                'percentage': segment.get('percentage', 0),
                'mask_path': segment.get('mask_path')
            })
            
            viz_config['legend'].append({
                'class_name': segment['class_name'],
                'color': segment.get('color_code', '#000000')
            })
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(viz_config, f, indent=2)


class RoadBoundaryAnalyzer:
    """Specialized analyzer for road boundary detection"""
    
    @staticmethod
    def detect_lane_lines(mask: np.ndarray, lane_class_id: int = 6) -> Dict:
        """
        Detect lane lines from segmentation mask
        
        Args:
            mask: Segmentation mask
            lane_class_id: Class ID for lane markings
            
        Returns:
            Lane line information
        """
        lane_mask = (mask == lane_class_id).astype(np.uint8)
        
        if np.sum(lane_mask) == 0:
            return {'lanes_detected': False}
        
        # Find lane positions
        h, w = mask.shape
        lane_positions = []
        
        for row_idx in range(h//2, h, h//10):  # Sample rows
            row = lane_mask[row_idx, :]
            lane_pixels = np.where(row == 1)[0]
            if len(lane_pixels) > 0:
                lane_positions.append({
                    'y': row_idx,
                    'x_positions': lane_pixels.tolist()
                })
        
        return {
            'lanes_detected': True,
            'num_lane_positions': len(lane_positions),
            'lane_positions': lane_positions
        }
    
    @staticmethod
    def calculate_road_curvature(lane_positions: List[Dict]) -> float:
        """
        Estimate road curvature from lane positions
        
        Args:
            lane_positions: List of lane position dictionaries
            
        Returns:
            Curvature estimate (0 = straight, higher = more curved)
        """
        if len(lane_positions) < 3:
            return 0.0
        
        # Simple curvature estimation using position variance
        x_positions = []
        for pos in lane_positions:
            if pos['x_positions']:
                x_positions.append(np.mean(pos['x_positions']))
        
        if len(x_positions) < 3:
            return 0.0
        
        # Calculate standard deviation as curvature indicator
        return float(np.std(x_positions))
