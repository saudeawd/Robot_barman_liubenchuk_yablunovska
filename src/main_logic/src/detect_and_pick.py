#!/usr/bin/env python3
import rospy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
from moveit_commander import MoveGroupCommander, RobotCommander, roscpp_initialize, roscpp_shutdown

bridge = CvBridge()
arm = None

def image_callback(msg):
    global arm
    img = bridge.imgmsg_to_cv2(msg, "bgr8")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_red = np.array([0, 100, 100])
    upper_red = np.array([10, 255, 255])
    mask = cv2.inRange(hsv, lower_red, upper_red)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cnt = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(cnt)

        cup_pose = arm.get_current_pose().pose
        cup_pose.position.x = 0.5
        cup_pose.position.y = 0.0
        cup_pose.position.z = 0.05
        arm.set_pose_target(cup_pose)
        arm.go(wait=True)
    cv2.imshow("Camera", img)
    cv2.waitKey(1)

if __name__ == "__main__":
    roscpp_initialize([])
    rospy.init_node("cup_detector")
    robot = RobotCommander()
    arm = MoveGroupCommander("xarm5_arm")
    rospy.Subscriber("/camera/color/image_raw", Image, image_callback)
    rospy.spin()
    roscpp_shutdown()

