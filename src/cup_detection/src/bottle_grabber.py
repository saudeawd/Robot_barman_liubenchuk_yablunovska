#!/usr/bin/env python3

import rospy
import math
import numpy as np
from geometry_msgs.msg import PointStamped
from xarm_msgs.srv import SetAxis, Move, GripperMove, GripperConfig, SetInt16
from xarm_msgs.msg import RobotMsg
import time

class RealBottleGrabber:
    
    def __init__(self):
        rospy.init_node('real_bottle_grabber')
        
        self.img_width = 640.0
        self.img_height = 480.0
        self.CALIB_PIXEL = (478.0, 343.0)
        
        self.CALIB_JOINTS_DEG = [20.5, 80.0, -50.0, -65.0, 4.0]
        
        self.SENS_J1_U = -0.005
        self.SENS_J2_V = -0.01
        self.SENS_FORWARD = 0.02
        
        self.joint_limits_deg = [
            [-360.0, 360.0],
            [-118.0, 120.0],
            [-225.0, 11.0],
            [-97.0, 180.0],
            [-360.0, 360.0]
        ]
        
        self.J4_SAFE_LIMIT_MIN = -65.0
        self.J4_SAFE_LIMIT_MAX = 80.0
        self.J1_SAFE_LIMIT_MIN = -90.0
        self.J1_SAFE_LIMIT_MAX = 90.0
        self.J2_SAFE_LIMIT_MIN = -60.0
        self.J2_SAFE_LIMIT_MAX = 70.0
        self.J3_SAFE_LIMIT_MIN = -120.0
        self.J3_SAFE_LIMIT_MAX = 30.0
        self.J5_SAFE_LIMIT_MIN = -120.0
        self.J5_SAFE_LIMIT_MAX = 120.0
        
        self.safe_limits = [
            [self.J1_SAFE_LIMIT_MIN, self.J1_SAFE_LIMIT_MAX],
            [self.J2_SAFE_LIMIT_MIN, self.J2_SAFE_LIMIT_MAX],
            [self.J3_SAFE_LIMIT_MIN, self.J3_SAFE_LIMIT_MAX],
            [self.J4_SAFE_LIMIT_MIN, self.J4_SAFE_LIMIT_MAX],
            [self.J5_SAFE_LIMIT_MIN, self.J5_SAFE_LIMIT_MAX]
        ]
        
        self.current_joints = [0.0] * 5
        self.current_state = 0
        self._moving = False
        self._in_emergency = False
        self._last_joint_check = rospy.Time.now()
        
        self.MOVE_SPEED_NORMAL = 0.25
        self.MOVE_SPEED_SLOW = 0.12
        self.MOVE_SPEED_GRASP = 0.06
        self.MOVE_ACCEL = 0.08
        
        self.init_services()
        rospy.Subscriber("/xarm/xarm_states", RobotMsg, self.state_callback) 
        rospy.Subscriber("/bottle_coords", PointStamped, self.bottle_callback)
        rospy.sleep(1.0)
        
        self.initialize_robot() 
        self.open_gripper()
        self.safe_home_position()

    def init_services(self):
        rospy.wait_for_service('/xarm/motion_ctrl')
        rospy.wait_for_service('/xarm/set_mode')
        rospy.wait_for_service('/xarm/set_state')
        rospy.wait_for_service('/xarm/gripper_config')
        rospy.wait_for_service('/xarm/gripper_move')
        rospy.wait_for_service('/xarm/move_joint')
        
        self.motion_ctrl = rospy.ServiceProxy('/xarm/motion_ctrl', SetAxis) 
        self.set_mode = rospy.ServiceProxy('/xarm/set_mode', SetInt16) 
        self.set_state = rospy.ServiceProxy('/xarm/set_state', SetInt16)
        self.gripper_config = rospy.ServiceProxy('/xarm/gripper_config', GripperConfig)
        self.gripper_move = rospy.ServiceProxy('/xarm/gripper_move', GripperMove)
        self.move_srv = rospy.ServiceProxy('/xarm/move_joint', Move) 

    def initialize_robot(self):
        try:
            self.set_mode(0)
            self.set_state(0)
            self.motion_ctrl(1, 1) 
            self.gripper_config(True)
        except Exception as e:
            raise
        
        rospy.sleep(0.5)

    def state_callback(self, msg):
        if len(msg.angle) >= 5:
            self.current_joints = [math.radians(a) for a in msg.angle[:5]]
        
        if hasattr(msg, 'state'):
            self.current_state = msg.state
        
        now = rospy.Time.now()
        if (now - self._last_joint_check).to_sec() > 0.5:
            self._last_joint_check = now
            self.check_current_joints_safety()

    def check_current_joints_safety(self):
        if not self.current_joints or len(self.current_joints) < 5:
            return True
            
        current_degrees = [math.degrees(j) for j in self.current_joints]
        is_safe = True
        
        for i, angle in enumerate(current_degrees):
            safe_min, safe_max = self.safe_limits[i]
            if angle < safe_min or angle > safe_max:
                is_safe = False
        
        if not is_safe:
            self.force_stop_robot()
            return False
        
        return True

    def force_stop_robot(self):
        try:
            try:
                self.set_state(9)
                rospy.sleep(0.5)
            except:
                pass
            
            try:
                self.set_state(5)
                rospy.sleep(0.5)
            except:
                pass
            
            rospy.sleep(1.0)
            
            try:
                self.set_state(0)
                rospy.sleep(0.5)
            except:
                pass
            
            self._in_emergency = True
            
        except Exception as e:
            pass

    def enforce_safe_limits(self, joint_angles_deg):
        safe_angles = []
        
        for i, angle in enumerate(joint_angles_deg):
            safe_min, safe_max = self.safe_limits[i]
            
            if angle < safe_min:
                angle = safe_min
            elif angle > safe_max:
                angle = safe_max
            
            official_min, official_max = self.joint_limits_deg[i]
            angle = max(min(angle, official_max), official_min)
            
            safe_angles.append(angle)
        
        return safe_angles

    def simple_ik_pixel_adjust(self, pixel_x, pixel_y):
        base_j1, base_j2, base_j3, base_j4, _ = self.CALIB_JOINTS_DEG
        calib_u, calib_v = self.CALIB_PIXEL
        
        delta_u = pixel_x - calib_u
        delta_v = pixel_y - calib_v
        
        max_delta = 20.0
        delta_u = max(min(delta_u, max_delta), -max_delta)
        delta_v = max(min(delta_v, max_delta), -max_delta)
        
        j1 = base_j1 + (delta_u * self.SENS_J1_U)
        
        max_j_change = 1.0
        
        forward_effect = delta_v * self.SENS_FORWARD
        vertical_effect = delta_v * self.SENS_J2_V
        
        j2_change = (forward_effect * 0.9) + (vertical_effect * 0.1)
        j3_change = (forward_effect * 0.1) + (vertical_effect * 0.9)
        
        j2_change = max(min(j2_change, max_j_change), -max_j_change)
        j3_change = max(min(j3_change, max_j_change), -max_j_change)
        
        j2 = base_j2 + j2_change
        j3 = base_j3 + j3_change
        
        calib_sum = base_j2 + base_j3 + base_j4
        j4 = calib_sum - j2 - j3
        
        if j4 < self.J4_SAFE_LIMIT_MIN:
            j4 = self.J4_SAFE_LIMIT_MIN
            j2 = base_j2
            j3 = base_j3
        
        j5 = self.CALIB_JOINTS_DEG[4]
        
        target_degrees = [j1, j2, j3, j4, j5]
        target_degrees = self.enforce_safe_limits(target_degrees)
        
        if target_degrees[3] < self.J4_SAFE_LIMIT_MIN:
            target_degrees[3] = self.J4_SAFE_LIMIT_MIN
        
        return [math.radians(j) for j in target_degrees]
    
    def verify_joint_safety(self, joint_degrees, operation_name=""):
        is_safe = True
        
        for i, angle in enumerate(joint_degrees):
            safe_min, safe_max = self.safe_limits[i]
            if angle < safe_min or angle > safe_max:
                is_safe = False
            
            if i == 3 and angle < self.J4_SAFE_LIMIT_MIN:
                is_safe = False
        
        if not is_safe:
            return False
        else:
            return True
    
    def check_before_move(self):
        if not self.check_current_joints_safety():
            return False
        
        if self.current_state == 5 or self.current_state == 9:
            try:
                self.set_state(0)
                rospy.sleep(0.5)
            except Exception as e:
                return False
        
        return True

    def safe_move_joint_real(self, target_joints_rad, duration=2.0, speed=None, accel=None):
        if not self.check_before_move():
            return False
        
        target_degrees = [math.degrees(j) for j in target_joints_rad]
        target_degrees = self.enforce_safe_limits(target_degrees)
        
        if target_degrees[3] < self.J4_SAFE_LIMIT_MIN:
            target_degrees[3] = self.J4_SAFE_LIMIT_MIN
        
        if not self.verify_joint_safety(target_degrees, "move"):
            return False
        
        move_speed = speed if speed is not None else self.MOVE_SPEED_NORMAL
        move_accel = accel if accel is not None else self.MOVE_ACCEL
        
        current_j4 = math.degrees(self.current_joints[3]) if len(self.current_joints) > 3 else 0
        distance = abs(target_degrees[3] - current_j4)
        move_time = max(0.8, min(distance / move_speed, 2.5))
        
        try:
            response = self.move_srv(
                target_degrees,
                move_speed,
                move_accel,
                0.0,
                0.0
            )
            
            if response.ret != 0:
                return False
            
            rospy.sleep(move_time)
            
            rospy.sleep(0.2)
            self.check_current_joints_safety()
            
            return True
            
        except Exception as e:
            return False

    def set_gripper_pulse(self, pulse_value):
        try:
            pulse_pos = int(np.clip(pulse_value, -10, 850))
            response = self.gripper_move(pulse_pos)
            time.sleep(1.2)
            return True
        except Exception as e:
            return False

    def open_gripper(self):
        self.set_gripper_pulse(850)

    def close_gripper_grasp(self):
        self.set_gripper_pulse(730)

    def safe_home_position(self):
        if not self.check_before_move():
            return False
            
        home_joints_rad = [0.0, 0.2, -0.3, -0.5, 0.0]
        return self.safe_move_joint_real(home_joints_rad, 2.5, self.MOVE_SPEED_NORMAL)

    def bottle_callback(self, msg):
        if self._moving:
            return
        self._moving = True
        
        try:
            pixel_u, pixel_v = msg.point.x, msg.point.y
            
            if not self.check_before_move():
                self._moving = False
                return
            
            self.open_gripper()
            
            target_joints_rad = self.simple_ik_pixel_adjust(pixel_u, pixel_v)
            target_deg = [math.degrees(j) for j in target_joints_rad]
            
            if not self.verify_joint_safety(target_deg, "bottle approach"):
                self.open_gripper()
                self.safe_home_position()
                self._moving = False
                return
            
            if not self.check_before_move():
                self._moving = False
                return
            
            self.safe_move_joint_real(target_joints_rad, 2.5, self.MOVE_SPEED_SLOW)
            rospy.sleep(1.0)
            
            self.close_gripper_grasp()
            rospy.sleep(1.8)
            
            lift_deg = [
                target_deg[0],
                max(target_deg[1] - 3.0, self.J2_SAFE_LIMIT_MIN),
                min(target_deg[2] + 1.5, self.J3_SAFE_LIMIT_MAX),
                target_deg[3],
                target_deg[4]
            ]
            lift_deg = self.enforce_safe_limits(lift_deg)
            
            if not self.verify_joint_safety(lift_deg, "lift"):
                self.open_gripper()
                self.safe_home_position()
                self._moving = False
                return
            
            if not self.check_before_move():
                self.open_gripper()
                self.safe_home_position()
                self._moving = False
                return
                
            lift_rad = [math.radians(j) for j in lift_deg]
            self.safe_move_joint_real(lift_rad, 1.8, self.MOVE_SPEED_SLOW)
            rospy.sleep(0.5)
            
            cup_deg = [
                lift_deg[0] + 12.0,
                max(lift_deg[1] + 6.0, self.J2_SAFE_LIMIT_MIN),
                lift_deg[2],
                lift_deg[3],
                lift_deg[4]
            ]
            cup_deg = self.enforce_safe_limits(cup_deg)
            
            if not self.verify_joint_safety(cup_deg, "cup approach"):
                self.open_gripper()
                self.safe_home_position()
                self._moving = False
                return
            
            if not self.check_before_move():
                self.open_gripper()
                self.safe_home_position()
                self._moving = False
                return
                
            cup_rad = [math.radians(j) for j in cup_deg]
            self.safe_move_joint_real(cup_rad, 2.2, self.MOVE_SPEED_SLOW)
            rospy.sleep(0.5)
            
            pour_deg = cup_deg.copy()
            pour_deg[4] = 60.0
            pour_deg = self.enforce_safe_limits(pour_deg)
            
            if not self.verify_joint_safety(pour_deg, "pour rotation"):
                self._moving = False
                return
            
            if not self.check_before_move():
                self._moving = False
                return
                
            pour_rad = [math.radians(j) for j in pour_deg]
            self.safe_move_joint_real(pour_rad, 1.8, self.MOVE_SPEED_SLOW)
            rospy.sleep(2.5)
            
            pour_deg[4] = 0.0
            pour_deg = self.enforce_safe_limits(pour_deg)
            
            if not self.verify_joint_safety(pour_deg, "pour return"):
                self._moving = False
                return
            
            if not self.check_before_move():
                self._moving = False
                return
                
            pour_rad = [math.radians(j) for j in pour_deg]
            self.safe_move_joint_real(pour_rad, 1.8, self.MOVE_SPEED_SLOW)
            rospy.sleep(0.5)
            
            lower_deg = pour_deg.copy()
            lower_deg[1] = min(lower_deg[1] + 2.5, self.J2_SAFE_LIMIT_MAX)
            lower_deg = self.enforce_safe_limits(lower_deg)
            
            if not self.verify_joint_safety(lower_deg, "lower"):
                self._moving = False
                return
            
            if not self.check_before_move():
                self._moving = False
                return
                
            lower_rad = [math.radians(j) for j in lower_deg]
            self.safe_move_joint_real(lower_rad, 1.5, self.MOVE_SPEED_SLOW)
            rospy.sleep(0.5)
            
            self.open_gripper()
            rospy.sleep(1.5)
            
            self.safe_home_position()
            
        except Exception as e:
            try:
                self.open_gripper()
                self.safe_home_position()
            except:
                pass
        finally:
            self._moving = False

    def run(self):
        rospy.spin()

if __name__ == "__main__":
    try:
        grabber = RealBottleGrabber()
        grabber.run()
    except Exception as e:
        pass
