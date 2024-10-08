# Loads the calibration files provided by Voyis and sets the stereo calibration offsets 
# To install this script, copy it to the following location:
# Windows: C:\Users\<username>\AppData\Local\Agisoft\Metashape Pro\scripts
# Mac: /Users/<username>/Library/Application Support/Agisoft/Metashape Pro/scripts
# Linux: /home/<username>/.Agisoft/Metashape Pro/scripts

# After copying the script, restart Metashape. The script will appear in a new Menu labeld Voyis.


import Metashape
import glob
import os
import json

# Checking compatibility
compatible_major_version = "2.1"
found_major_version = ".".join(Metashape.app.version.split('.')[:2])
if found_major_version != compatible_major_version:
    raise Exception("Incompatible Metashape version: {} != {}".format(found_major_version, compatible_major_version))

def loadCalibration(calibration_folder, chunk):
    # check to see if the calibration file exists
    if not os.path.exists(calibration_folder):
        raise Exception("Calibration file does not exist {}".format(calibration_folder))

    calibs = dict()
    calibs["left"] = Metashape.Calibration()
    calibs["right"] = Metashape.Calibration()

    left_file = glob.glob(os.path.join(calibration_folder, "*_cam0.xml"))
    right_file = glob.glob(os.path.join(calibration_folder, "*_cam1.xml"))

    calibs["left"].load(left_file[0])
    calibs["right"].load(right_file[0])

    # create the sensors and set the calibration
    sensors = dict()
    sensors["left"] = chunk.addSensor()
    sensors["right"] = chunk.addSensor()
    sensors["left"].label = "left"
    sensors["right"].label = "right"
    sensors["right"].master = sensors["left"]

    for sensor in sensors.keys():
        calib = calibs[sensor]
        sensors[sensor].width = calib.width
        sensors[sensor].height = calib.height
        sensors[sensor].type = calib.type
        sensors[sensor].user_calib = calib
        sensors[sensor].fixed = True

    # load the stereo calibration offsets
    with open(
        os.path.join(os.path.join(calibration_folder, "AgisoftSlaveOffsets.json"))
    ) as f:
        extrinsics = json.load(f)

        sensors["right"].reference.enabled = True

        # you MUST set this.. and its does not match gui and it is not documented at all. Like at all
        # this is the same as checking "adjust location" in the gui / camera calibration tab under slave offsets
        # I would like the last 4 hours of my life back please
        sensors["right"].fixed_location = False
        sensors["right"].fixed_rotation = False

        # yes.. you have to set this for the left sensor too. In soviet Russia left sensor moves you. Dont know why. Dont ask why. Just do it.
        sensors["left"].fixed_location = False

        # set the rotation and translation for the right sensor and set accuracy to a high value to be "constant"
        # In soviet Russia, nothing is fixed! Just solidly attached to the left sensor
        sensors["right"].reference.location = Metashape.Vector(
            [extrinsics["x"], extrinsics["y"], extrinsics["z"]]
        )
        sensors["right"].reference.location_accuracy = Metashape.Vector(
            [1e-6, 1e-6, 1e-6]
        )
        sensors["right"].reference.location_enabled = True

        # at least this part makes some sense. Had to find it by looking at the python console output. Like a real programmer.
        sensors["right"].reference.rotation = Metashape.Vector(
            [extrinsics["Omega"], extrinsics["Kappa"], extrinsics["Phi"]]
        )
        sensors["right"].reference.rotation_accuracy = Metashape.Vector(
            [1e-6, 1e-6, 1e-6]
        )
        sensors["right"].reference.rotation_enabled = True

        sensors["right"].location = Metashape.Vector(
            [extrinsics["x"], extrinsics["y"], extrinsics["z"]]
        )
        sensors["right"].rotation = Metashape.Matrix(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0, 0, 1.0]]
        )

    # assign the calibrations to the cameras
    for cam in chunk.cameras:
        base = os.path.basename(cam.photo.path)
        # if basename has "left in it assign to left grouping with sensor
        # else assign to right grouping with sensor
        if "left" in base:
            cam.sensor = sensors["left"]
        else:
            cam.sensor = sensors["right"]
            


def load_voyis_stereo_calibration():
    folder = Metashape.app.getExistingDirectory("Select calibration folder")
    chunk = Metashape.app.document.chunk
    if chunk is None:
        raise Exception("Empty project!")
    
    loadCalibration(folder, chunk)
    print("Voyis stereo calibration loaded")
    return True


label = "Voyis/Load Stereo Calibration"
Metashape.app.addMenuItem(label, load_voyis_stereo_calibration)