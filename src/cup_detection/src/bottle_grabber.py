#!/usr/bin/env python3
import rospy
import cv2
import numpy as np
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from geometry_msgs.msg import PointStamped
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.msg import GripperCommandActionGoal
import math
from collections import deque

bridge = CvBridge()
bottle_history = deque(maxlen=5)

# Камера параметри (приклад, заміни на свої з calibration.yaml)
fx, fy = 615.0, 615.0
cx_cam, cy_cam = 320.0, 240.0
depth_default = 0.5  # якщо немає depth sensor, приблизна відстань до пляшки

# Грипер
class Gripper:
    def __init__(self):
        self.pub = rospy.Publisher(
            "/xarm/gripper_controller/gripper_cmd/goal",
            GripperCommandActionGoal,
            queue_size=10
        )
    def close(self):
        goal = GripperCommandActionGoal()
        goal.goal.command.position = 0.0
        goal.goal.command.max_effort = 50.0
        self.pub.publish(goal)
        rospy.loginfo("Gripper closed")

# Контролер руки
class Arm:
    def __init__(self):
        from trajectory_arm_controller import TrajectoryArmController
        self.arm = TrajectoryArmController()
        self.arm.go_ready()
    def move_to(self, x, y, z):
        return self.arm.move_to_cup_with_waypoints(x, y, z)
    def go_ready(self):
        self.arm.go_ready()

# Пікселі -> координати в метрах
def pixel_to_world(px, py, depth=depth_default):
    X = (px - cx_cam) * depth / fx
    Y = (py - cy_cam) * depth / fy
    Z = depth
    return X, Y, Z

# Згладжування детекцій
def smooth_detection(history, new):
    if new is None:
        return history[-1] if history else None
    history.append(new)
    cx_avg = int(np.mean([d['cx'] for d in history]))
    cy_avg = int(np.mean([d['cy'] for d in history]))
    return {'cx': cx_avg, 'cy': cy_avg}

# Детектор + рух руки
class BottleHandler:
    def __init__(self, arm, gripper):
        self.arm = arm
        self.gripper = gripper
        self.moving = False
        rospy.Subscriber("/arm_camera/image_raw", Image, self.callback)

    def callback(self, msg):
        if self.moving:
            return
        frame = bridge.imgmsg_to_cv2(msg, "bgr8")
        # Проста детекція кольору пляшки (замість YOLO для прикладу)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))  # червоний
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return
        c = max(contours, key=cv2.contourArea)
        M = cv2.moments(c)
        if M["m00"] == 0:
            return
        cx = int(M["m10"]/M["m00"])
        cy = int(M["m01"]/M["m00"])
        smoothed = smooth_detection(bottle_history, {'cx': cx, 'cy': cy})
        self.handle_bottle(smoothed)

    def handle_bottle(self, detection):
        if detection is None:
            return
        self.moving = True
        x, y, z = pixel_to_world(detection['cx'], detection['cy'])
        rospy.loginfo(f"Moving to bottle at world coords: {x:.2f}, {y:.2f}, {z:.2f}")
        success = self.arm.move_to(x, y, z)
        if success:
            rospy.sleep(0.5)
            self.gripper.close()
            rospy.sleep(1.0)
            self.arm.go_ready()
        self.moving = False

if __name__ == "__main__":
    rospy.init_node("bottle_grabber")
    arm = Arm()
    gripper = Gripper()
    handler = BottleHandler(arm, gripper)
    rospy.spin()
