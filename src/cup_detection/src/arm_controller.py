#!/usr/bin/env python3

import rospy
from geometry_msgs.msg import PointStamped
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.msg import JointTrajectoryControllerState
import math

class TrajectoryArmController:
    def __init__(self):
        rospy.init_node('trajectory_arm_controller', anonymous=True)
        self.trajectory_pub = rospy.Publisher(
            '/xarm/xarm5_traj_controller/command',
            JointTrajectory,
            queue_size=10
        )
        self.state_sub = rospy.Subscriber(
            '/xarm/xarm5_traj_controller/state',
            JointTrajectoryControllerState,
            self.state_callback
        )
        self.cup_sub = rospy.Subscriber(
            '/target_cup_position', 
            PointStamped, 
            self.cup_callback
        )
        self.joint_names = [
            'joint1',
            'joint2',
            'joint3',
            'joint4',
            'joint5'
        ]
        self.current_positions = None
        self.moving = False
        self.last_target_time = rospy.Time.now()
        rospy.sleep(1.0)
        rospy.loginfo("=== Trajectory Arm Controller Ready ===")
        rospy.loginfo(f"Joint names: {self.joint_names}")
        rospy.loginfo("Publishing to: /xarm/xarm5_traj_controller/command")
    
    def state_callback(self, msg):
        self.current_positions = list(msg.actual.positions)
    
    def send_trajectory(self, positions, duration=3.0):
        if len(positions) != 5:
            rospy.logwarn(f"Expected 5 joint positions, got {len(positions)}")
            return False
        trajectory = JointTrajectory()
        trajectory.header.stamp = rospy.Time.now()
        trajectory.joint_names = self.joint_names
        point = JointTrajectoryPoint()
        point.positions = positions
        point.velocities = [0.0] * 5
        point.time_from_start = rospy.Duration(duration)
        trajectory.points.append(point)
        self.trajectory_pub.publish(trajectory)
        rospy.loginfo(f"Sent trajectory: {[f'{p:.3f}' for p in positions]} (duration: {duration}s)")
        return True
    
    def send_smooth_trajectory(self, waypoints, durations):
        trajectory = JointTrajectory()
        trajectory.header.stamp = rospy.Time.now()
        trajectory.joint_names = self.joint_names
        for positions, duration in zip(waypoints, durations):
            point = JointTrajectoryPoint()
            point.positions = positions
            point.velocities = [0.0] * 5
            point.time_from_start = rospy.Duration(duration)
            trajectory.points.append(point)
        self.trajectory_pub.publish(trajectory)
        rospy.loginfo(f"Sent smooth trajectory with {len(waypoints)} waypoints")
    
    def go_home(self):
        rospy.loginfo("Moving to HOME position")
        home_position = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.send_trajectory(home_position, duration=3.0)
        rospy.sleep(3.5)
    
    def go_ready(self):
        rospy.loginfo("Moving to READY position")
        ready_position = [0.0, -0.6, 1.0, -0.4, 0.0]
        self.send_trajectory(ready_position, duration=2.5)
        rospy.sleep(3.0)
    
    def go_observe(self):
        rospy.loginfo("Moving to OBSERVE position")
        observe_position = [0.0, -0.4, 0.8, -0.4, 0.0]
        self.send_trajectory(observe_position, duration=2.0)
        rospy.sleep(2.5)
    
    def calculate_reach_position(self, x, y, z):
        base_angle = math.atan2(y, x)
        horizontal_distance = math.sqrt(x**2 + y**2)
        L1 = 0.0
        L2 = 0.3
        L3 = 0.3
        L4 = 0.2
        target_z = z - L1
        target_r = horizontal_distance
        target_r_wrist = target_r - L4 * 0.5
        d = math.sqrt(target_r_wrist**2 + target_z**2)
        if d > (L2 + L3):
            rospy.logwarn(f"Target too far! Distance: {d:.3f}, max reach: {L2 + L3:.3f}")
            d = L2 + L3 - 0.05
        try:
            cos_elbow = (L2**2 + L3**2 - d**2) / (2 * L2 * L3)
            cos_elbow = max(-1.0, min(1.0, cos_elbow))
            elbow_angle = math.acos(cos_elbow)
            alpha = math.atan2(target_z, target_r_wrist)
            beta = math.asin((L3 * math.sin(elbow_angle)) / d)
            shoulder_angle = -(alpha + beta)
            wrist_angle = -(shoulder_angle + elbow_angle)
        except Exception as e:
            rospy.logwarn(f"IK calculation error: {e}")
            shoulder_angle = -0.8
            elbow_angle = 1.2
            wrist_angle = -0.4
        joint_positions = [
            base_angle,
            shoulder_angle,
            elbow_angle,
            wrist_angle,
            0.0
        ]
        return joint_positions
    
    def move_to_cup_with_waypoints(self, x, y, z):
        rospy.loginfo(f"Planning movement to cup at ({x:.3f}, {y:.3f}, {z:.3f})")
        try:
            target_position = self.calculate_reach_position(x, y, z + 0.15)
            approach_position = self.calculate_reach_position(x, y, z + 0.08)
            waypoints = [
                target_position,
                approach_position,
            ]
            durations = [2.5, 4.0]
            self.send_smooth_trajectory(waypoints, durations)
            rospy.sleep(4.5)
            rospy.loginfo("Reached cup position!")
            return True
        except Exception as e:
            rospy.logerr(f"Error moving to cup: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def cup_callback(self, msg):
        current_time = rospy.Time.now()
        if self.moving:
            rospy.loginfo_throttle(1.0, "Already moving, ignoring new target")
            return
        time_since_last = (current_time - self.last_target_time).to_sec()
        if time_since_last < 5.0:
            return
        self.last_target_time = current_time
        self.moving = True
        x = msg.point.x
        y = msg.point.y
        z = msg.point.z
        rospy.loginfo("="*50)
        rospy.loginfo(f"NEW TARGET: Cup at ({x:.3f}, {y:.3f}, {z:.3f})")
        rospy.loginfo("="*50)
        try:
            rospy.loginfo("Step 1: Moving to observation position...")
            self.go_observe()
            rospy.loginfo("Step 2: Moving to cup...")
            success = self.move_to_cup_with_waypoints(x, y, z)
            if success:
                rospy.loginfo("Step 3: Returning to ready position...")
                rospy.sleep(1.0)
                self.go_ready()
            else:
                rospy.logwarn("Failed to reach cup, returning home")
                self.go_home()
            rospy.loginfo("Movement sequence completed!")
            rospy.loginfo("="*50)
        except Exception as e:
            rospy.logerr(f"Error in cup callback: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.go_home()
            except:
                pass
        finally:
            self.moving = False
    
    def run(self):
        rospy.loginfo("\n" + "="*50)
        rospy.loginfo("Trajectory Arm Controller is READY!")
        rospy.loginfo("Waiting for cup positions from detector...")
        rospy.loginfo("Press Ctrl+C to stop")
        rospy.loginfo("="*50 + "\n")
        rospy.sleep(2.0)
        if self.current_positions is not None:
            rospy.loginfo(f"Current joint positions: {[f'{p:.3f}' for p in self.current_positions]}")
        self.go_home()
        rospy.sleep(2.0)
        self.go_ready()
        rospy.spin()

if __name__ == '__main__':
    try:
        controller = TrajectoryArmController()
        controller.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("Trajectory Arm Controller stopped")
    except Exception as e:
        rospy.logerr(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
