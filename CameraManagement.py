import time
import cv2 as cv
import numpy as np

from queue import Queue
from pypylon import pylon, genicam


class ImageEventHandler(pylon.ImageEventHandler):
    imageQueue = Queue()

    def OnImageGrabbed(self, camera, grab_result):
        try:
            while not self.imageQueue.empty():
                self.imageQueue.get()
            if grab_result.GrabSucceeded():
                cameraContextValue = grab_result.GetCameraContext()
                with grab_result.GetArrayZeroCopy() as ZCArray:
                    grabbedImage = ZCArray
                self.imageQueue.put((cameraContextValue, grabbedImage.data))
        except genicam.GenericException as e:
            print("ImageEventHandler Exception: {}".format(e))
        finally:
            grab_result.Release()


class Camera:
    # This class will save all the information coming from the pypylon package, so that two instances of a CW can be created.
    # Cameras are initialised using their serial number (see the CW serial number).
    # Subclassing a pylon.InstantCamera is not supported, so this camera1 will be used as an attribute.
    # See https://github.com/basler/pypylon/issues/196
    def __init__(self, serial_number=None, grayscale=True):
        super(Camera, self).__init__()
        self.serialNumber = serial_number
        self.grayScale = grayscale
        # Parameters for continuous extraction of data:
        self.info = pylon.CDeviceInfo()
        self.camera = None
        self.imageEventHandler = ImageEventHandler()
        self.setCamera()
        self.registerGrabbingStrategy()

        # Open camera briefly to avoid errors.
        self.camera.Open()
        self.pixelWidth = self.camera.Width.Value
        self.pixelHeight = self.camera.Height.Value
        self.camera.Close()

    def getShape(self):
        return self.pixelWidth, self.pixelHeight

    def formatImage(self, image_to_format):
        if len(image_to_format.shape) == 3 and self.grayScale:
            image_to_format = cv.cvtColor(image_to_format, cv.COLOR_RGB2GRAY)
        return image_to_format

    def setCamera(self):
        try:
            if self.serialNumber is None:
                self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
            else:
                self.info.SetSerialNumber(self.serialNumber)
                self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(self.info))
            print("Camera {} is connected.".format(self.serialNumber))
        except genicam.GenericException as e:
            raise SystemExit('Camera {} could not be found: {}'.format(self.serialNumber, e))

    def Open(self):
        if not self.camera.IsOpen():
            self.camera.Open()

    def Close(self):
        if self.camera.IsGrabbing():
            self.camera.StopGrabbing()
        if self.camera.IsOpen():
            self.camera.Close()

    def Destroy(self):
        self.Close()
        self.camera.DetachDevice()
        self.camera.DestroyDevice()

    def registerGrabbingStrategy(self):
        self.camera.RegisterConfiguration(pylon.SoftwareTriggerConfiguration(), pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)
        self.camera.RegisterImageEventHandler(self.imageEventHandler, pylon.RegistrationMode_Append, pylon.Cleanup_Delete)

    def grabImage(self, image):
        self.Open()
        grabbedImage = None
        if not self.camera.IsGrabbing():
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly, pylon.GrabLoop_ProvidedByInstantCamera)
        try:
            if self.camera.WaitForFrameTriggerReady(0, pylon.TimeoutHandling_Return):
                self.camera.ExecuteSoftwareTrigger()
            while grabbedImage is None:
                _, grabbedImage = self.imageEventHandler.imageQueue.get()
            np.copyto(image, self.formatImage(grabbedImage))
            return 0
        except genicam.RuntimeException as e:
            print('Runtime Exception: {}'.format(e))
            return -1


class CameraArray:
    def __init__(self, serial_numbers=(), grayscale=True):
        super(CameraArray, self).__init__()
        self.serialNumbers = serial_numbers
        self.grayScale = grayscale
        # Parameters for continuous extraction of data:
        self.numCameras = len(self.serialNumbers)
        if self.numCameras == 0 or self.numCameras > 4:
            raise ValueError
        self.cameraArray = pylon.InstantCameraArray(self.numCameras)
        self.pixelWidths, self.pixelHeights = [], []
        self.imageEventHandler = ImageEventHandler()
        self.setCameras()

        # Open cameras briefly to avoid errors.
        for camera in self.cameraArray:
            camera.Open()
            self.pixelWidths.append(camera.Width.Value)
            self.pixelHeights.append(camera.Height.Value)
            camera.Close()

    def getShape(self):
        return self.pixelWidths, self.pixelHeights

    def formatImage(self, image_to_format):
        if len(image_to_format.shape) == 3 and self.grayScale:
            image_to_format = cv.cvtColor(image_to_format, cv.COLOR_RGB2GRAY)
        return image_to_format.astype('uint8')

    def registerGrabbingStrategy(self, camera):
        camera.RegisterConfiguration(pylon.SoftwareTriggerConfiguration(), pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)
        camera.RegisterImageEventHandler(self.imageEventHandler, pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)

    def setCameras(self):
        try:
            for serialNumber, camera in zip(self.serialNumbers, self.cameraArray):
                info = pylon.CDeviceInfo()
                info.SetSerialNumber(serialNumber)
                device = pylon.TlFactory.GetInstance().CreateDevice(info)
                camera.Attach(device)
                self.registerGrabbingStrategy(camera)
            print("Cameras", self.serialNumbers, "are connected.")
        except genicam.GenericException as e:
            raise SystemExit('Cameras {} could not be found: {}'.format(self.serialNumbers, e))

    def Open(self):
        self.cameraArray.Open()

    def Close(self):
        if self.cameraArray.IsGrabbing():
            self.cameraArray.StopGrabbing()
        if self.cameraArray.IsOpen():
            self.cameraArray.Close()

    def Destroy(self):
        self.Close()
        self.cameraArray.DestroyDevice()

    def imageFromQueue(self):
        return self.imageEventHandler.imageQueue.get

    def grabImage(self, images):
        if not self.cameraArray.IsGrabbing():
            self.cameraArray.StartGrabbing(pylon.GrabStrategy_LatestImageOnly, pylon.GrabLoop_ProvidedByInstantCamera)
        try:
            for cam in self.cameraArray:
                if cam.WaitForFrameTriggerReady(10, pylon.TimeoutHandling_ThrowException):
                    cam.ExecuteSoftwareTrigger()
            for _ in range(2):
                context, grabbedImage = self.imageEventHandler.imageQueue.get()
                np.copyto(images[context], self.formatImage(grabbedImage))
            return 0
        except genicam.RuntimeException as e:
            print('Runtime Exception: {}'.format(e))
            return -1


def runSingleCamera():
    # This works well
    camera = Camera("22290932")
    testWindow = 'window1'
    cv.namedWindow(testWindow)
    cv.moveWindow(testWindow, 20, 20)

    h, w = camera.getShape()
    image = np.zeros((w, h), dtype=np.uint8)

    start = time.time()
    while True:
        if camera.grabImage(image) != 0:
            continue

        cv.imshow(testWindow, cv.resize(image, (int(h/4), int(w/4))))
        if cv.waitKey(1) & 0xFF == 27:  # Exit upon escape key
            break
        now = time.time()
        print("FPS =", 1 / (time.time() - start))
        start = now
    camera.Destroy()
    cv.destroyAllWindows()


def runCameraArray():
    cameras = CameraArray(["21565643", "22290932"])
    testWindow = 'window1'
    cv.namedWindow(testWindow)
    cv.moveWindow(testWindow, 20, 20)

    def hconcat_resize_min(im_list, interpolation=cv.INTER_CUBIC):
        im_list = [cv.resize(image, (int(image.shape[1] / 4), int(image.shape[0] / 4))) for image in im_list]
        h_min = min(im.shape[0] for im in im_list)
        im_list_resize = [cv.resize(im, (int(im.shape[1] * h_min / im.shape[0]), h_min), interpolation=interpolation)
                          for im in im_list]
        return cv.hconcat(im_list_resize)

    images = [np.zeros((w, h), dtype=np.uint8) for w, h in cameras.getShape()]

    start = time.time()
    while True:
        if cameras.grabImage(images) != 0:
            continue

        cv.imshow(testWindow, hconcat_resize_min(images))
        if cv.waitKey(1) & 0xFF == 27:  # Exit upon escape key
            break
        now = time.time()
        print("FPS =", 1 / (time.time() - start))
        start = now
    cameras.Destroy()
    cv.destroyAllWindows()


def runCamerasAlternate():
    cameraOn = Camera("21565643")
    cameraOff = Camera("22290932")
    testWindow = 'window1'
    cv.namedWindow(testWindow)
    cv.moveWindow(testWindow, 20, 20)

    h, w = cameraOn.getShape()
    imageOn = np.zeros((w, h), dtype=np.uint8)

    start = time.time()
    while True:
        if cameraOn.grabImage(imageOn) != 0:
            continue

        cv.imshow(testWindow, cv.resize(imageOn, (int(h/4), int(w/4))))
        if cv.waitKey(1) & 0xFF == 27:  # Exit upon escape key
            break

        if cv.waitKey(5) & 0xFF == ord('q'):  # Switch cameras
            cameraOn.Close()
            cameraOn, cameraOff = cameraOff, cameraOn
            cameraOn.Open()
            h, w = cameraOn.getShape()
            imageOn = np.zeros((w, h), dtype=np.uint8)

        now = time.time()
        print("FPS =", 1 / (time.time() - start))
        start = now
    cameraOn.Destroy()
    cameraOn.Destroy()
    cv.destroyAllWindows()


if __name__ == '__main__':
    runCamerasAlternate()

