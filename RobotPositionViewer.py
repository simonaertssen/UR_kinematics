import sys
import matplotlib
import numpy as np
import time

from RobotClass import Robot
from Kinematics import ForwardKinematics
# from lib.Kinematics import ForwardKinematics

from PyQt5 import QtCore, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
matplotlib.use('Qt4Agg')


class ThreeDimCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, frameon=False)
        super(ThreeDimCanvas, self).__init__(self.fig)
        self.axes = self.fig.gca(projection='3d')  # generates 3D Axes object

        self.axes.set_xlim3d(-0.5, 0.5)
        self.axes.set_ylim3d(-0.5, 0.5)
        self.axes.set_zlim3d(0, 1)

        self.axes.set_xlabel('$X$')
        self.axes.set_ylabel('$Y$')
        self.axes.set_zlabel('$Z$')

        self.axes.view_init(35, -145)

        initPos = np.zeros((6,))
        self.arms   = self.axes.plot3D(initPos, initPos, initPos, 'black')[0]
        self.joints = self.axes.scatter3D(initPos, initPos, initPos, c='r')

    def updatePlot(self, positions):
        X, Y, Z = positions
        self.arms.set_data_3d(X, Y, Z)
        self.joints._offsets3d = (X, Y, Z)
        self.draw_idle()


class RobotJointReader(QtCore.QThread):
    def __init__(self, read_joints, update_plot, print_me=None):
        super(RobotJointReader, self).__init__()
        self.readJoints = read_joints
        self.updatePlot = update_plot
        self.printMe = print_me
        self.running = True

    def run(self):
        while self.running:
            self.updatePlot(self.readJoints())
            # if callable(self.printMe):
                # print(self.printMe())
                # print([value*180/np.pi for value in self.printMe()])


class Viewer(QtWidgets.QMainWindow):
    def __init__(self, robot):
        super(Viewer, self).__init__()
        self.setWindowTitle("Viewing the robot position")
        self.resize(1000, 500)

        self.shutdownRobot = robot.shutdownSafely

        self.canvas = ThreeDimCanvas(self, width=6, height=6, dpi=75)
        self.setCentralWidget(self.canvas)

        self.jointReader = RobotJointReader(robot.getJointPositions, self.canvas.updatePlot)
        self.jointReader.start()
        # time.sleep(0.1)
        self.show()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.closeEvent(event)

    def closeEvent(self, event):
        self.jointReader.running = False
        self.jointReader.wait()
        self.shutdownRobot()
        self.close()


class RobotRotationEmulator:
    # Emulate movements of the robot to use the viewer without a robot
    def __init__(self):
        super(RobotRotationEmulator, self).__init__()
        # Initial angles of the robot:
        # self.angles = [0, -np.pi/2, 0, -np.pi/2, 0, 0]
        self.angles = [item * np.pi / 180 for item in [61.42, -93.0, 94.65, -91.59, -90.0, 0.0]]

    def step(self):
        self.angles[0] += 0.0005

    def getJointPositions(self):
        self.step()
        return ForwardKinematics(self.angles)

    def shutdownSafely(self):
        pass

    def getJointAngles(self):
        return self.angles


def seeViewerAtWork(robot):
    app = QtWidgets.QApplication(sys.argv)
    w = Viewer(robot)
    sys.exit(app.exec_())


def seeViewerAtWorkWithEmulator():
    r = RobotRotationEmulator()
    seeViewerAtWork(r)


def seeViewerAtWorkWithRobot():
    r = Robot()
    seeViewerAtWork(r)


if __name__ == '__main__':
    seeViewerAtWorkWithEmulator()



