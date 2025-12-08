#!/usr/bin/env python3
import rospy
import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import PointStamped, Pose
from moveit_commander import MoveGroupCommander, RobotCommander, PlanningSceneInterface
import moveit_commander
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import numpy as np

class MoveItArmController:
    def __init__(self):
        rospy.init_node('moveit_arm_controller', anonymous=True)
        moveit_commander.roscpp_initialize([])
        
        self.robot = RobotCommander()
        self.scene = PlanningSceneInterface()
        self.group = MoveGroupCommander("xarm5")
        
        self.group.set_planning_time(10)
        self.group.set_max_velocity_scaling_factor(0.2)
        self.group.set_max_acceleration_scaling_factor(0.2)
        
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        
        self.bridge = CvBridge()
        self.depth_image = None
        self.camera_info = None
        
        # Можливі варіанти топіків для RealSense
        depth_topics = [
            "/camera/depth/image_raw",
            "/camera/aligned_depth_to_color/image_raw",
            "/camera/depth/image_rect_raw",
            "/depth/image_raw"
        ]
        
        camera_info_topics = [
            "/camera/depth/camera_info",
            "/camera/color/camera_info",
            "/camera/rgb/camera_info"
        ]
        
        # Знаходимо доступні топіки
        available_topics = rospy.get_published_topics()
        available_topic_names = [t[0] for t in available_topics]
        
        depth_topic = None
        for topic in depth_topics:
            if topic in available_topic_names:
                depth_topic = topic
                break
        
        camera_info_topic = None
        for topic in camera_info_topics:
            if topic in available_topic_names:
                camera_info_topic = topic
                break
        
        if depth_topic:
            rospy.loginfo(f"Subscribing to depth topic: {depth_topic}")
            self.depth_sub = rospy.Subscriber(depth_topic, Image, self.depth_callback)
        else:
            rospy.logerr("No depth topic found! Available topics:")
            for topic in available_topic_names:
                if 'depth' in topic.lower():
                    rospy.logerr(f"  - {topic}")
        
        if camera_info_topic:
            rospy.loginfo(f"Subscribing to camera info topic: {camera_info_topic}")
            self.camera_info_sub = rospy.Subscriber(camera_info_topic, CameraInfo, self.camera_info_callback)
        else:
            rospy.logerr("No camera info topic found! Available topics:")
            for topic in available_topic_names:
                if 'camera_info' in topic.lower():
                    rospy.logerr(f"  - {topic}")
        
        self.cup_sub = rospy.Subscriber("/cup_coords", PointStamped, self.cup_callback)
        
        self.moving = False
        
        rospy.loginfo("MoveIt Arm Controller Ready!")
        if depth_topic and camera_info_topic:
            rospy.loginfo("Waiting for camera info and depth image...")
        else:
            rospy.logwarn("Some camera topics not found - depth conversion may not work!")
    
    def depth_callback(self, msg):
        try:
            self.depth_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            # Логуємо інформацію про зображення один раз
            if not hasattr(self, '_depth_logged'):
                rospy.loginfo(f"Depth image shape: {self.depth_image.shape}, dtype: {self.depth_image.dtype}")
                self._depth_logged = True
        except Exception as e:
            rospy.logerr(f"Error converting depth image: {e}")
    
    def camera_info_callback(self, msg):
        self.camera_info = msg
        if self.camera_info:
            rospy.loginfo_once("Camera info received")
    
    def pixel_to_3d(self, u, v, depth):
        """Конвертація піксельних координат у 3D координати"""
        if self.camera_info is None:
            rospy.logerr("No camera info available!")
            return None
        
        # Отримуємо параметри камери
        fx = self.camera_info.K[0]  # focal length x
        fy = self.camera_info.K[4]  # focal length y
        cx = self.camera_info.K[2]  # principal point x
        cy = self.camera_info.K[5]  # principal point y
        
        # Конвертація в метри (depth зазвичай в міліметрах для RealSense)
        z = depth / 1000.0
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy
        
        return x, y, z
    
    def cup_callback(self, msg):
        if self.moving:
            rospy.loginfo_throttle(1.0, "Already moving, ignoring new target")
            return
        
        if self.depth_image is None:
            rospy.logwarn_throttle(2.0, "No depth image available yet")
            return
        
        if self.camera_info is None:
            rospy.logwarn_throttle(2.0, "No camera info available yet")
            return
        
        self.moving = True
        try:
            # msg.point містить піксельні координати
            u = int(msg.point.x)
            v = int(msg.point.y)
            
            rospy.loginfo(f"Received cup at pixel coordinates: u={u}, v={v}")
            
            # Отримуємо глибину в цій точці
            if u < 0 or v < 0 or v >= self.depth_image.shape[0] or u >= self.depth_image.shape[1]:
                rospy.logerr(f"Pixel coordinates out of bounds: u={u}, v={v}")
                return
            
            # Якщо зображення має кілька каналів, беремо перший
            if len(self.depth_image.shape) > 2:
                depth_value = self.depth_image[v, u, 0]
            else:
                depth_value = self.depth_image[v, u]
            
            # Конвертуємо в скаляр
            depth = np.asscalar(depth_value) if hasattr(np, 'asscalar') else depth_value.item()
            
            rospy.loginfo(f"Raw depth value: {depth}, type: {type(depth)}")
            
            if depth == 0 or depth != depth:  # depth != depth перевіряє на NaN
                rospy.logwarn("No valid depth at cup location, using neighborhood average")
                # Спробуємо взяти середнє значення з околиці 5x5 пікселів
                region = self.depth_image[max(0, v-2):min(self.depth_image.shape[0], v+3),
                                         max(0, u-2):min(self.depth_image.shape[1], u+3)]
                
                # Якщо багатоканальне зображення
                if len(region.shape) > 2:
                    region = region[:, :, 0]
                
                valid_depths = region[(region > 0) & (region == region)]  # виключаємо 0 та NaN
                if len(valid_depths) > 0:
                    depth = float(np.median(valid_depths))
                else:
                    rospy.logerr("No valid depth data around cup location")
                    return
            
            rospy.loginfo(f"Depth at cup: {depth} mm")
            
            # Конвертуємо піксельні координати в 3D
            x, y, z = self.pixel_to_3d(u, v, depth)
            
            rospy.loginfo(f"Cup 3D position in camera frame: x={x:.3f}, y={y:.3f}, z={z:.3f} m")
            
            # Перевірка чи глибина реалістична (кубок має бути далі ніж 20 см від камери)
            if z < 0.2:
                rospy.logwarn(f"Depth too small ({z:.3f}m). Cup might be too close or depth invalid.")
                # Не повертаємось, а продовжуємо - можливо це все ж правильно
            
            # Створюємо PointStamped у системі координат камери
            cup_point_camera = PointStamped()
            cup_point_camera.header.frame_id = msg.header.frame_id
            cup_point_camera.header.stamp = rospy.Time(0)
            cup_point_camera.point.x = x
            cup_point_camera.point.y = y
            cup_point_camera.point.z = z
            
            # Трансформація з камери у базу робота
            transform = self.tf_buffer.lookup_transform(
                "link_base", 
                msg.header.frame_id,
                rospy.Time(0),
                rospy.Duration(1.0)
            )
            
            cup_point = tf2_geometry_msgs.do_transform_point(cup_point_camera, transform)
            
            rospy.loginfo(f"Cup position in base frame: x={cup_point.point.x:.3f}, y={cup_point.point.y:.3f}, z={cup_point.point.z:.3f} m")
            
            # Перевірка досяжності (xarm5 має досяжність ~0.7 метра)
            distance = (cup_point.point.x**2 + cup_point.point.y**2 + cup_point.point.z**2)**0.5
            if distance > 0.7:
                rospy.logwarn(f"Cup too far away: {distance:.3f}m (max ~0.7m). Check calibration!")
                return
            
            # Підхід через waypoint: спершу над кубком, потім вниз
            waypoints = []
            
            # Отримуємо поточну орієнтацію ефектора
            current_pose = self.group.get_current_pose().pose
            rospy.loginfo(f"Current end effector position: x={current_pose.position.x:.3f}, y={current_pose.position.y:.3f}, z={current_pose.position.z:.3f}")
            
            # Над кубком (0.15 m зверху для безпеки)
            pose_over = Pose()
            pose_over.position.x = cup_point.point.x
            pose_over.position.y = cup_point.point.y
            pose_over.position.z = cup_point.point.z + 0.15
            # Використовуємо поточну орієнтацію замість фіксованої
            pose_over.orientation = current_pose.orientation
            
            rospy.loginfo(f"Target position: x={pose_over.position.x:.3f}, y={pose_over.position.y:.3f}, z={pose_over.position.z:.3f}")
            
            # Спочатку просто спробуємо дістатись над кубком
            self.group.set_pose_target(pose_over)
            self.group.set_planning_time(10)
            
            rospy.loginfo("Planning path to position above cup...")
            plan = self.group.plan()
            
            # plan може бути tuple (success, trajectory, planning_time, error_code) або trajectory
            if isinstance(plan, tuple):
                success = plan[0]
                trajectory = plan[1]
            else:
                success = True
                trajectory = plan
            
            if success and trajectory and hasattr(trajectory, 'joint_trajectory') and len(trajectory.joint_trajectory.points) > 0:
                rospy.loginfo("Path found! Executing...")
                self.group.execute(trajectory, wait=True)
                rospy.loginfo("Successfully reached position above cup!")
                
                # Тепер опустимось нижче
                pose_near = Pose()
                pose_near.position.x = cup_point.point.x
                pose_near.position.y = cup_point.point.y
                pose_near.position.z = cup_point.point.z + 0.05
                pose_near.orientation = current_pose.orientation
                
                self.group.set_pose_target(pose_near)
                plan2 = self.group.plan()
                
                if isinstance(plan2, tuple):
                    success2 = plan2[0]
                    trajectory2 = plan2[1]
                else:
                    success2 = True
                    trajectory2 = plan2
                
                if success2 and trajectory2 and hasattr(trajectory2, 'joint_trajectory') and len(trajectory2.joint_trajectory.points) > 0:
                    self.group.execute(trajectory2, wait=True)
                    rospy.loginfo("Reached cup!")
                else:
                    rospy.logwarn("Could not plan path to lower position")
            else:
                rospy.logerr("Failed to plan path to cup. Position might be unreachable.")
                rospy.loginfo(f"Try manually checking if position ({pose_over.position.x:.3f}, {pose_over.position.y:.3f}, {pose_over.position.z:.3f}) is reachable")
                
        except tf2_ros.LookupException as e:
            rospy.logerr(f"TF lookup error: {e}")
        except tf2_ros.ExtrapolationException as e:
            rospy.logerr(f"TF extrapolation error: {e}")
        except Exception as e:
            rospy.logerr(f"Error moving to cup: {e}")
            import traceback
            rospy.logerr(traceback.format_exc())
        finally:
            self.moving = False
    
    def run(self):
        rospy.spin()

if __name__ == "__main__":
    try:
        controller = MoveItArmController()
        controller.run()
    except rospy.ROSInterruptException:
        pass