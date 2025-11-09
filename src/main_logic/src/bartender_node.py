#!/usr/bin/env python3
import rospy
import moveit_commander
import sys

def main():
    moveit_commander.roscpp_initialize(sys.argv)
    rospy.init_node('bartender_node')

    arm = moveit_commander.MoveGroupCommander("xarm5")  # або "xarm6"
    rospy.loginfo("Готовий рухатись!")

    arm.set_named_target("home")
    arm.go(wait=True)

    rospy.loginfo("Повернувся в home позицію.")

if __name__ == "__main__":
    main()

