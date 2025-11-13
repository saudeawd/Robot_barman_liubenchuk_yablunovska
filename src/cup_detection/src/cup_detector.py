#!/usr/bin/env python3

import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import PointStamped, Point
from cv_bridge import CvBridge
from std_msgs.msg import Header

class CupDetector:
    def __init__(self):
        rospy.init_node('cup_detector', anonymous=True)
        self.bridge = CvBridge()
        self.image_sub = rospy.Subscriber('/arm_camera/image_raw', Image, self.image_callback)
        self.cup_position_pub = rospy.Publisher('/target_cup_position', PointStamped, queue_size=10)
        self.debug_image_pub = rospy.Publisher('/cup_detection/debug_image', Image, queue_size=10)
        self.mask_image_pub = rospy.Publisher('/cup_detection/mask_image', Image, queue_size=1)
        self.frame_count = 0
        self.process_every_n_frames = 3
        rospy.loginfo("=== Cup Detector Started ===")
        rospy.loginfo("Subscribed to: /arm_camera/image_raw")
        rospy.loginfo("Publishing to: /target_cup_position")
        rospy.loginfo("Debug images: /cup_detection/debug_image")
        rospy.loginfo("Mask images: /cup_detection/mask_image")

    def detect_cups(self, image):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([100, 80, 40])
        upper_blue = np.array([135, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cups = []
        height, width = image.shape[:2]
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 2000:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = float(h) / w if w > 0 else 0
                if 1.0 < aspect_ratio < 3.5:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    bottom_y = y + h
                    cups.append({
                        'bbox': (x, y, w, h),
                        'center': (center_x, center_y),
                        'bottom': (center_x, bottom_y),
                        'area': area,
                        'y_position': center_y
                    })
        return cups, mask
    
    def pixel_to_world(self, pixel_x, pixel_y, image_width, image_height):
        center_x = image_width / 2.0
        center_y = image_height / 2.0
        delta_x = pixel_x - center_x
        delta_y = pixel_y - center_y
        scale_x = 0.0012
        scale_y = 0.0012
        camera_offset_x = 0.5
        camera_offset_y = 0.0
        offset_x = delta_x * scale_x
        offset_y = delta_y * scale_y
        world_x = camera_offset_x + offset_y
        world_y = camera_offset_y + offset_x
        world_z = 0.82
        rospy.loginfo_throttle(3.0, 
            f"Pixel ({pixel_x}, {pixel_y}) -> "
            f"Offset ({offset_x:.3f}, {offset_y:.3f}) -> "
            f"World ({world_x:.3f}, {world_y:.3f}, {world_z:.3f})")
        return world_x, world_y, world_z
    
    def image_callback(self, msg):
        self.frame_count += 1
        if self.frame_count % self.process_every_n_frames != 0:
            return
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            height, width = cv_image.shape[:2]
            cups, mask = self.detect_cups(cv_image)
            debug_image = cv_image.copy()
            if len(cups) > 0:
                cups.sort(key=lambda x: x['y_position'], reverse=True)
                for i, cup in enumerate(cups):
                    x, y, w, h = cup['bbox']
                    center_x, center_y = cup['center']
                    color = (0, 255, 0) if i == 0 else (255, 255, 0)
                    thickness = 3 if i == 0 else 2
                    cv2.rectangle(debug_image, (x, y), (x + w, y + h), color, thickness)
                    cv2.circle(debug_image, (center_x, center_y), 8, color, -1)
                    label = f"TARGET #{i+1}" if i == 0 else f"Cup #{i+1}"
                    cv2.putText(debug_image, label, (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                target_cup = cups[0]
                center_x, center_y = target_cup['center']
                world_x, world_y, world_z = self.pixel_to_world(center_x, center_y, width, height)
                cup_point = PointStamped()
                cup_point.header = Header()
                cup_point.header.stamp = rospy.Time.now()
                cup_point.header.frame_id = "world"
                cup_point.point.x = world_x
                cup_point.point.y = world_y
                cup_point.point.z = world_z
                self.cup_position_pub.publish(cup_point)
                rospy.loginfo_throttle(2.0, 
                    f"Target cup: pixel({center_x}, {center_y}) -> "
                    f"world({world_x:.3f}, {world_y:.3f}, {world_z:.3f})")
                info_text = f"Cups detected: {len(cups)}"
                cv2.putText(debug_image, info_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                coord_text = f"Target: ({world_x:.2f}, {world_y:.2f}, {world_z:.2f})"
                cv2.putText(debug_image, coord_text, (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(debug_image, "No cups detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            try:
                debug_msg = self.bridge.cv2_to_imgmsg(debug_image, "bgr8")
                self.debug_image_pub.publish(debug_msg)
                
                mask_msg = self.bridge.cv2_to_imgmsg(mask, "mono8")
                self.mask_image_pub.publish(mask_msg)
            except Exception as e:
                rospy.logwarn(f"Failed to publish debug image or mask: {e}")
        except Exception as e:
            rospy.logerr(f"Error processing image: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        rospy.loginfo("Cup detector ready! Waiting for images...")
        rospy.spin()

if __name__ == '__main__':
    try:
        detector = CupDetector()
        detector.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("Cup detector stopped")
    except Exception as e:
        rospy.logerr(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()