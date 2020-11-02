import time
from RobotClass import Robot
from CameraManagement import TopCamera, DetailCamera
from threading import Thread

import cv2


class MainManager(Thread):
    def __init__(self):
        super(MainManager, self).__init__(daemon=True)
        self.running = True
        self.robot = None
        self.topCam = None
        self.detailCam = None
        self.actions = dict()
        self.tryConnect()
        self.start()

    def tryConnect(self):
        def startAsync(attribute, constructor):
            setattr(self, attribute, constructor())
        startThreads = [Thread(target=startAsync, args=('robot', Robot,)),
                        Thread(target=startAsync, args=('topCam', TopCamera,)),
                        Thread(target=startAsync, args=('detailCam', DetailCamera,))]
        [x.start() for x in startThreads]
        [x.join() for x in startThreads]

    def run(self):
        while self.running:
            for function_name, function_to_call in self.actions.items():
                # print(function_name)
                try:
                    function_to_call()
                except TypeError as e:
                    print('An uncallable function was encountered: {}'.format(e))

    def shutdownAllComponents(self):
        self.running = False
        self.join()
        shutdownThreads = [Thread(target=self.robot.shutdownSafely),
                           Thread(target=self.topCam.Shutdown),
                           Thread(target=self.detailCam.Shutdown)]
        [x.start() for x in shutdownThreads]
        [x.join() for x in shutdownThreads]

    def checkComponentsAreConnected(self):
        return self.isRobotConnected() and self.isModBusConnected() and self.isTopCameraConnected() and self.isDetailCameraConnected()

    def isRobotConnected(self):
        try:
            return self.robot.RobotCCO.Connected
        except:
            return False

    def isModBusConnected(self):
        try:
            return self.robot.ModBusReader.Connected
        except:
            return False

    def isTopCameraConnected(self):
        try:
            return self.topCam.Connected
        except:
            return False

    def isDetailCameraConnected(self):
        try:
            return self.detailCam.Connected
        except:
            return False

    def getContinuousImages(self, continuous_image_callback, continuous_info_callback):
        if not callable(continuous_image_callback):
            raise ValueError('Continuous Image Callback not callable')
        if not callable(continuous_info_callback):
            raise ValueError('Continuous Info Callback not callable')

        def wrap_callback():
            output = self.topCam.grabImage()
            if output:
                continuous_image_callback(output[0])
            elif len(output) > 1:
                continuous_info_callback(output[1:])
        self.actions[str(continuous_image_callback)] = wrap_callback

    def test(self):
        print('Testing')

    def moveToolTo(self, target_position, move, wait=True, check_collisions=True):
        self.robot.moveTo(target_position, move, wait=wait, check_collisions=check_collisions, p=True)

    def moveJointsTo(self, target_position, move, wait=True, check_collisions=True):
        self.robot.moveTo(target_position, move, wait=wait, check_collisions=check_collisions, p=False)


if __name__ == '__main__':
    print('Before')
    c = MainManager()
    time.sleep(10)
    print(c.checkComponentsAreConnected())
    time.sleep(10)
    print('After')
