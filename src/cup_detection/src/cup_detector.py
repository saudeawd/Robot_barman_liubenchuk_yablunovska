#!/usr/bin/env python3
import rospy
from sensor_msgs.msg import Image
from geometry_msgs.msg import PointStamped
import cv2
from cv_bridge import CvBridge
import numpy as np
import onnxruntime as ort
from collections import deque

model_path = "yolov8n.onnx"
session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])

bottle_pub = rospy.Publisher('/bottle_coords', PointStamped, queue_size=10)
cup_pub = rospy.Publisher('/cup_coords', PointStamped, queue_size=10)

bridge = CvBridge()

RELEVANT_CLASSES = {
    39: 'bottle',
    40: 'wine_glass', 
    41: 'cup'
}

bottle_history = deque(maxlen=5)
cup_history = deque(maxlen=5)

def preprocess(img):
    h, w = img.shape[:2]
    img_in = cv2.resize(img, (640, 640))
    img_in = cv2.cvtColor(img_in, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img_in = np.transpose(img_in, (2, 0, 1))
    img_in = np.expand_dims(img_in, axis=0)
    return img_in, w, h

def nms(boxes, scores, iou_threshold=0.5):
    if len(boxes) == 0:
        return []
    
    boxes = np.array(boxes)
    scores = np.array(scores)
    
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        intersection = w * h
        
        iou = intersection / (areas[i] + areas[order[1:]] - intersection)
        
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    
    return keep

def smooth_detection(history, new_detection):
    if new_detection is None:
        if len(history) > 0:
            return history[-1]
        return None
    
    history.append(new_detection)
    
    if len(history) > 0:
        cx_avg = int(np.mean([d['cx'] for d in history]))
        cy_avg = int(np.mean([d['cy'] for d in history]))
        conf_avg = np.mean([d['conf'] for d in history])
        
        return {
            'cx': cx_avg,
            'cy': cy_avg,
            'conf': conf_avg,
            'x1': new_detection['x1'],
            'y1': new_detection['y1'],
            'x2': new_detection['x2'],
            'y2': new_detection['y2']
        }
    
    return new_detection

def callback(msg):
    frame = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
    orig_h, orig_w = frame.shape[:2]
    
    input_tensor, _, _ = preprocess(frame)
    
    outputs = session.run(None, {session.get_inputs()[0].name: input_tensor})
    predictions = outputs[0]
    
    if len(predictions.shape) == 3:
        predictions = predictions[0]
        predictions = predictions.T
    
    boxes_xywh = predictions[:, :4]
    class_scores = predictions[:, 4:]
    
    class_ids = np.argmax(class_scores, axis=1)
    confidences = np.max(class_scores, axis=1)
    
    mask = confidences > 0.2
    boxes_xywh = boxes_xywh[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]
    
    bottle_boxes = []
    bottle_scores = []
    cup_boxes = []
    cup_scores = []
    
    for box_xywh, cls, conf in zip(boxes_xywh, class_ids, confidences):
        if cls not in [39, 40, 41]:
            continue
        
        x_center_norm, y_center_norm, width_norm, height_norm = box_xywh
        
        x_center_640 = x_center_norm * 640
        y_center_640 = y_center_norm * 640
        width_640 = width_norm * 640
        height_640 = height_norm * 640
        
        x1_640 = x_center_640 - width_640 / 2
        y1_640 = y_center_640 - height_640 / 2
        x2_640 = x_center_640 + width_640 / 2
        y2_640 = y_center_640 + height_640 / 2
        
        scale_x = orig_w / 640.0
        scale_y = orig_h / 640.0
        
        x1 = int(x1_640 * scale_x)
        y1 = int(y1_640 * scale_y)
        x2 = int(x2_640 * scale_x)
        y2 = int(y2_640 * scale_y)
        
        x1 = max(0, min(x1, orig_w - 1))
        y1 = max(0, min(y1, orig_h - 1))
        x2 = max(0, min(x2, orig_w - 1))
        y2 = max(0, min(y2, orig_h - 1))
        
        if x2 <= x1 or y2 <= y1:
            continue
        
        box = [x1, y1, x2, y2]
        
        if cls == 39:
            bottle_boxes.append(box)
            bottle_scores.append(conf)
        elif cls in [40, 41]:
            cup_boxes.append(box)
            cup_scores.append(conf)
    
    bottle_indices = nms(bottle_boxes, bottle_scores, iou_threshold=0.5)
    cup_indices = nms(cup_boxes, cup_scores, iou_threshold=0.5)
    
    detection_count = 0
    
    bottle_detection = None
    for idx in bottle_indices:
        x1, y1, x2, y2 = bottle_boxes[idx]
        conf = bottle_scores[idx]
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        
        if idx == bottle_indices[0]:
            bottle_detection = {
                'cx': cx, 'cy': cy, 'conf': conf,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
            }
        break
    
    bottle_smoothed = smooth_detection(bottle_history, bottle_detection)
    
    if bottle_smoothed:
        detection_count += 1
        x1, y1, x2, y2 = bottle_smoothed['x1'], bottle_smoothed['y1'], bottle_smoothed['x2'], bottle_smoothed['y2']
        cx, cy = bottle_smoothed['cx'], bottle_smoothed['cy']
        conf = bottle_smoothed['conf']
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
        label = f"bottle {conf:.2f}"
        cv2.putText(frame, label, (x1, y1 - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        ps = PointStamped()
        ps.header.stamp = rospy.Time.now()
        ps.header.frame_id = "camera"
        ps.point.x = float(cx)
        ps.point.y = float(cy)
        ps.point.z = 0.0
        bottle_pub.publish(ps)
        rospy.loginfo_throttle(2, f"Bottle: ({cx},{cy}), Conf={conf:.2f}")
    
    cup_detection = None
    for idx in cup_indices:
        x1, y1, x2, y2 = cup_boxes[idx]
        conf = cup_scores[idx]
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        
        if idx == cup_indices[0]:
            cup_detection = {
                'cx': cx, 'cy': cy, 'conf': conf,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
            }
        break
    
    cup_smoothed = smooth_detection(cup_history, cup_detection)
    
    if cup_smoothed:
        detection_count += 1
        x1, y1, x2, y2 = cup_smoothed['x1'], cup_smoothed['y1'], cup_smoothed['x2'], cup_smoothed['y2']
        cx, cy = cup_smoothed['cx'], cup_smoothed['cy']
        conf = cup_smoothed['conf']
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
        label = f"cup {conf:.2f}"
        cv2.putText(frame, label, (x1, y1 - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        ps = PointStamped()
        ps.header.stamp = rospy.Time.now()
        ps.header.frame_id = "camera"
        ps.point.x = float(cx)
        ps.point.y = float(cy)
        ps.point.z = 0.0
        cup_pub.publish(ps)
        rospy.loginfo_throttle(2, f"Cup: ({cx},{cy}), Conf={conf:.2f}")
    
    cv2.putText(frame, f"Detections: {detection_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    cv2.imshow("Cup Detection", frame)
    cv2.waitKey(1)

rospy.init_node('cup_detector')
rospy.Subscriber('/usb_cam/image_raw', Image, callback)
rospy.spin()
cv2.destroyAllWindows()
