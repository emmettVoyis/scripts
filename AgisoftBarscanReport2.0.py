import Metashape
import os
import sys
import time
import glob
import json
import numpy as np
import reportlab
import pandas as pd
import uuid

import re

# parse the voyisCalibFile
import glob
from tqdm import tqdm
from pqdm.processes import pqdm
import shutil


# Checking compatibility
compatible_major_version = "2.1"
found_major_version = ".".join(Metashape.app.version.split('.')[:2])
if found_major_version != compatible_major_version:
    raise Exception("Incompatible Metashape version: {} != {}".format(found_major_version, compatible_major_version))


def find_files(folder, types):
    return [
        entry.path
        for entry in os.scandir(folder)
        if (entry.is_file() and os.path.splitext(entry.name)[1].lower() in types)
    ]


class ScaleBar:
    def __init__(self, name, marker_1_name, marker_2_name, ground_truth_distance):
        self.name = name
        self.marker_1_name = marker_1_name
        self.marker_2_name = marker_2_name
        self.ground_truth_distance = ground_truth_distance
        self.measured_distance = None

    def error(self):
        return (
            self.measured_distance - self.ground_truth_distance
        )

    def absError(self):
        return abs(self.measured_distance - self.ground_truth_distance)

    def errorPercent(self):
        return self.error() / self.ground_truth_distance * 100



# globally define the scale bars for the bar scan
ScaleBars = [
    # this controls what is measured and reported on
    #ScaleBar("Marker 1 to Marker 4", "target 1", "target 4", 1.74343),
    #ScaleBar("Marker 2 to Marker 5", "target 2", "target 5", 1.70071),
    #ScaleBar("Marker 3 to Marker 6", "target 3", "target 6", 1.68541), 
    
    #ScaleBar("Marker 1 to Marker 7", "target 1", "target 7", 4.01371),
    #ScaleBar("Marker 2 to Marker 8", "target 2", "target 8", 4.06376),
    #ScaleBar("Marker 3 to Marker 9", "target 3", "target 9", 3.83347),

    #ScaleBar("Marker 1 to Marker 10", "target 1", "target 10", 5.51932),
    #ScaleBar("Marker 2 to Marker 11", "target 2", "target 11", 5.77972),
    #ScaleBar("Marker 3 to Marker 12", "target 3", "target 12", 5.68031),

    #ScaleBar("Marker 1 to Marker 13", "target 1", "target 13", 3.68595),
    #ScaleBar("Marker 2 to Marker 14", "target 2", "target 14", 3.68664),
    #ScaleBar("Marker 3 to Marker 15", "target 3", "target 15", 3.48525),

    #ScaleBar("Marker 1 to Marker 16", "target 1", "target 16", 4.37563),
    #ScaleBar("Marker 2 to Marker 17", "target 2", "target 17", 4.41734),
    #ScaleBar("Marker 3 to Marker 18", "target 3", "target 18", 4.17691),

    ScaleBar("Marker 1 to Marker 10", "target 1", "target 10", 5.5193),
    ScaleBar("Marker 1 to Marker 11", "target 1", "target 11", 5.6597),
    ScaleBar("Marker 1 to Marker 12", "target 1", "target 12", 5.6929), 
    
    ScaleBar("Marker 2 to Marker 10", "target 2", "target 10", 5.6409),
    ScaleBar("Marker 2 to Marker 11", "target 2", "target 11", 5.7797),
    ScaleBar("Marker 2 to Marker 12", "target 2", "target 12", 5.8100),

    ScaleBar("Marker 3 to Marker 10", "target 3", "target 10", 5.5102),
    ScaleBar("Marker 3 to Marker 11", "target 3", "target 11", 5.6494),
    ScaleBar("Marker 3 to Marker 12", "target 3", "target 12", 5.6803)
]

def getSerialIdFromFolder(folder):
    # get the serial id from the folder path using regex to find the serial id
    serial_id = re.search(r"(\d{9})", folder).group(1)
    return serial_id


class BarScanAnalizer:
    def __init__(self, verification_folder, camera_calibration_file):
        self.serial_id = getSerialIdFromFolder(verification_folder) 
        self.uuid = uuid.uuid4()
        self.image_folder = verification_folder
        self.output_folder = os.path.join(verification_folder, "{}_Verification-{}".format(self.serial_id, time.strftime("%Y-%m-%d_%H-%M-%S")))
        self.calibration_folder = os.path.join(camera_calibration_file)
        self.cal_uuid = ""
        
        self.output_file = os.path.join(
            self.output_folder, f"{self.serial_id}.psx")

        self.doc = Metashape.Document()
        self.chunk = self.doc.addChunk()
        self.calibs = dict()

        self.loadCalibration()
        self.getFiles()
        
        # these dictate if a scan passes or fails
        self.passing_error_in_percentage = 0.03
        self.passing_single_measurment_error_percentage = 0.04

    def save(self):
        self.doc.save(self.output_file)
        self.doc.open(self.output_file)

    def loadCalibration(self):

        print("loading calibration from {}".format(self.calibration_folder))

        self.calibs["left"] = Metashape.Calibration()
        self.calibs["right"] = Metashape.Calibration()

        self.calibs["left"].load(os.path.join(self.calibration_folder, "{}_cam0.xml".format(self.serial_id)))
        self.calibs["right"].load(os.path.join(self.calibration_folder, "{}_cam1.xml".format(self.serial_id)))

        self.sensors = dict()
        self.sensors["left"] = self.chunk.addSensor()
        self.sensors["right"] = self.chunk.addSensor()
        self.sensors["left"].label = "left"
        self.sensors["right"].label = "right"
        self.sensors["right"].master = self.sensors["left"]

        for sensor in self.sensors.keys():
            calib = self.calibs[sensor]
            self.sensors[sensor].width = calib.width
            self.sensors[sensor].height = calib.height
            self.sensors[sensor].type = calib.type
            self.sensors[sensor].user_calib = calib
            self.sensors[sensor].fixed = True

        # load the stereo calibration offsets
        with open(
            os.path.join(os.path.join(self.calibration_folder, "AgisoftSlaveOffsets.json"))
        ) as f:
            extrinsics = json.load(f)

            self.sensors["right"].reference.enabled = True

            # you MUST set this.. and its does not match gui and it is not documented at all. Like at all
            # this is the same as checking "adjust location" in the gui / camera calibration tab under slave offsets
            # I would like the last 4 hours of my life back please
            self.sensors["right"].fixed_location = False
            self.sensors["right"].fixed_rotation = False

            # yes.. you have to set this for the left sensor too. In soviet Russia left sensor moves you. Dont know why. Dont ask why. Just do it.
            self.sensors["left"].fixed_location = False

            # set the rotation and translation for the right sensor and set accuracy to a high value to be "constant"
            # In soviet Russia, nothing is fixed! Just solidly attached to the left sensor
            self.sensors["right"].reference.location = Metashape.Vector(
                [extrinsics["x"], extrinsics["y"], extrinsics["z"]]
            )
            self.sensors["right"].reference.location_accuracy = Metashape.Vector(
                [1e-5, 1e-5, 1e-5]
            )
            self.sensors["right"].reference.location_enabled = True

            # at least this part makes some sense. Had to find it by looking at the python console output. Like a real programmer.
            self.sensors["right"].reference.rotation = Metashape.Vector(
                [extrinsics["Omega"], extrinsics["Kappa"], extrinsics["Phi"]]
            )
            self.sensors["right"].reference.rotation_accuracy = Metashape.Vector(
                [1e-5, 1e-5, 1e-5]
            )
            self.sensors["right"].reference.rotation_enabled = True

            self.sensors["right"].location = Metashape.Vector(
                [extrinsics["x"], extrinsics["y"], extrinsics["z"]]
            )
            self.sensors["right"].rotation = Metashape.Matrix(
                [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0, 0, 1.0]]
            )
            
    def getFiles(self):

        # check to see if the folder / shortcut exists
        if not os.path.exists(self.image_folder):
            raise Exception("Verification image folder {} does not exist".format(self.image_folder))

        print("loading images from {}".format(self.image_folder))

        # recursively search for all images in the folder
        images = glob.glob("{}/**/*.jpg".format(os.path.normpath(self.image_folder)), recursive=True)
        images.extend(glob.glob("{}/**/*.jpeg".format(os.path.normpath(self.image_folder)), recursive=True))

        if len(images) == 0:
            images = glob.glob("{}/**/*.tif".format(os.path.normpath(self.image_folder)), recursive=True)
            


        # now associate the images into right and left pairs. Order is left, right, left, right, etc. This is done by looking at the last part of the filename which contains the sequence number
        # example: image_left_processed_SYSTEM_2023-11-08T153950.040882_CAL_11820.jpg. The value after CAL_ is the sequence number
        sorted_images = sorted(
            images, key=lambda x: os.path.basename(x).split("_")[-1])
        print(sorted_images)

        # create a list of filegroups. This is a list of integers that defines the multi-camera system groups. Basically it tells metashape that the first 2 images are a group, the next 2 are a group, etc.
        filegroups = [2] * (len(sorted_images) // 2)

        # images is alternating list of left and right paths
        self.chunk.addPhotos(
            sorted_images,
            filegroups=filegroups,
            layout=Metashape.MultiplaneLayout,
            load_reference=False,
        )

        # a sensor is what we call a camera, and a camera in metashape is a "Pose" in the VSLAM world. So we need to assign the sensor to each "keyframe or camera" in the chunk
        for cam in self.chunk.cameras:
            base = os.path.basename(cam.photo.path)
            # if basename has "left in it assign to left grouping with sensor
            # else assign to right grouping with sensor
            if "left" in base:
                cam.sensor = self.sensors["left"]
            else:
                cam.sensor = self.sensors["right"]

    # the first part of making a model is to align the cameras and make a sparse point cloud
    def align(self):
        print(str(len(self.chunk.cameras)) + " images loaded")

        self.chunk.matchPhotos(
            downscale=2,
            keypoint_limit=50000,
            tiepoint_limit=5000,
            generic_preselection=True, # enable or disable global matching of photos based on similarity
            reference_preselection=True, # enable or disable matching photos with some kind of prior knowledge. In this case we know every photo comes in order
            reference_preselection_mode = Metashape.ReferencePreselectionMode.ReferencePreselectionSequential
        )
        self.chunk.alignCameras()

    def load(self, file):
        self.doc = Metashape.Document()
        # self.doc.open(self.output_file)
        self.doc.open(os.path.join(file))

    def optimize_cameras(self, chunk, calcVariance=False):
        chunk.optimizeCameras(
            fit_f=False,
            fit_cx=False,
            fit_cy=False,
            fit_b1=False,
            fit_b2=False,
            fit_k1=False,
            fit_k2=False,
            fit_k3=False,
            fit_k4=False,
            fit_p1=False,
            fit_p2=False,
            fit_corrections=False,
            adaptive_fitting=False,
            tiepoint_covariance=calcVariance,
        )

    def filterBadPoints(self):
        print("filtering points with only 2 observations")
        # remove points with less than 3 observations
        chunk = self.doc.chunks[0]
        # filter out bad points by removing points that only have 2 or less observations
        f = Metashape.TiePoints.Filter()
        img_count = 2
        f.init(chunk, criterion=Metashape.TiePoints.Filter.ImageCount)
        f.selectPoints(img_count)
        f.removePoints(img_count)

        self.optimize_cameras(chunk)

        #remove points with high reconstruction uncertainty
        print("filtering points with high reconstruction uncertainty")

        for reconstruction_uncertainty in range(100, 20, -20):
            f = Metashape.TiePoints.Filter()
            f.init(
                chunk,
                criterion=Metashape.TiePoints.Filter.ReconstructionUncertainty,
            )
            f.removePoints(reconstruction_uncertainty)
            self.optimize_cameras(chunk)

        # remove points with low projection Accuracy
        print("filtering with low projection uncertainty")
        for projection_accuracy in range(90, 20, -20):
            f = Metashape.TiePoints.Filter()
            f.init(chunk, criterion=Metashape.TiePoints.Filter.ProjectionAccuracy)
            f.removePoints(projection_accuracy)
            self.optimize_cameras(chunk)

        # remove points with high reprojection error 
        print("filtering points with high reprojection error")
        for reprojection_error in np.arange(1.2, 0.5, -0.2):
            f = Metashape.TiePoints.Filter()
            f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
            f.removePoints(reprojection_error)
            self.optimize_cameras(chunk)

        # one last calc with the variance for saving
        self.optimize_cameras(chunk, calcVariance=True)


    '''generate a report of the scale bar measurments'''
    def generateReport(self):
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        has_passed = True

        # make output folder if it does not exist
        os.makedirs(self.output_folder, exist_ok=True)

        c = canvas.Canvas(
            os.path.join(self.output_folder,
                        "{}_Verification_Results_{}.pdf".format(self.serial_id, time.strftime("%Y-%m-%d_%H-%M-%S"))),
             pagesize=letter
        )

        c.setFont("Helvetica-Bold", 18)
        c.drawString(200, 750, f"{self.serial_id} Verification Report")

        # prepare the table
        measurment_table = [
            [
                "Measurment",
                "GT [m]",
                "Measured [m]",
                "Error [mm]",
                "Error %",
                "Pass/Fail",
            ]
        ]

        for scale_bar in ScaleBars:
            measurment_table.append(
                [
                    scale_bar.name,
                    "{:.4f}".format(scale_bar.ground_truth_distance),
                    "{:.4f}".format(scale_bar.measured_distance),
                    "{:.2f}".format(scale_bar.error() * 1000),
                    "{:.3f}".format(scale_bar.errorPercent()),
                    # fail if over 0.5 mm / meter of the ground truth distance. This is a 0.05% error 
                    "Pass" if abs(scale_bar.errorPercent()) < self.passing_single_measurment_error_percentage else "Fail",
                ]
            )

        from reportlab.platypus import Table, TableStyle

        table = Table(measurment_table)

        # Get the number of rows and columns in the table
        num_rows, col = len(measurment_table), len(measurment_table[0]) - 1

        # Define the style for cells based on their values
        style = TableStyle([])

        for row in range(1, num_rows):
            col = 5
            cell_value = measurment_table[row][col]
            cell_color = "RED" if cell_value == "Fail" else "GREEN"
            if cell_color:
                style.add('BACKGROUND', (col, row), (col, row), cell_color)

        style.add("GRID", (0, 0), (-1, -1), 0.5, "black")
        table.setStyle(style)

        # Calculate the available width and height for the table based on the page size
        available_width, available_height = letter

        # Get the table width and height
        table_width, table_height = table.wrapOn(
            c, available_width, available_height)

        # Calculate the starting position for the table to center it horizontally
        start_x = (available_width - table_width) / 2

        # Calculate the starting position for the table to place it below the previous content
        start_y = available_height - table_height - 100

        # Draw the table at the calculated position
        table.drawOn(c, start_x, start_y)

        # summarize the results as Root Mean square error
        rms = np.sqrt(
            np.mean([(scale_bar.errorPercent()/100) ** 2 for scale_bar in ScaleBars]))
        
        # check if the rms error is less than the passing error
        has_passed = rms * 100 < self.passing_error_in_percentage
        
        start_y = start_y - 20
        c.setFont("Helvetica-Bold", 12)
        c.drawString(start_x, start_y,
                     f"Root Mean Square Error [%]: {rms * 100:.4f}")
                      
        start_y = start_y - 13
        c.drawString(start_x, start_y, f"Passing Error [%]: {self.passing_error_in_percentage} %")

        start_y = start_y - 13

        if has_passed:
            c.drawString(start_x, start_y, "PASS")
        else:
            c.drawString(start_x, start_y, "FAIL")
        c.save()

        return has_passed

    def detectAndReportScaleBars(self):
        for chunk in self.doc.chunks:
            # detect markers
            chunk.detectMarkers(
                target_type=Metashape.CircularTarget12bit,
                tolerance=15,
                filter_mask=False,
                inverted=False,
            )

            chunk.refineMarkers()

            # get the list of markers
            markers = chunk.markers
            marker_dict = dict()

            # make a dict with the marker names
            for marker in markers:
                marker_dict[marker.label] = marker

            # take all the measurements
            for scale_bar in ScaleBars:
                marker_1 = marker_dict[scale_bar.marker_1_name]
                marker_2 = marker_dict[scale_bar.marker_2_name]
                bar = chunk.addScalebar(marker_1, marker_2)

                # YOU NEED TO SCALE YOUR MEASUREMENTS BY THE CHUNK SCALE TO GET THE REAL WORLD MEASUREMENTS
                # In soviet Russia, the chunk scale scales you
                # This is where 3.5 hours of Stan's time went to die
                dist = (
                    marker_1.position - marker_2.position
                ).norm() * chunk.transform.scale
                scale_bar.measured_distance = dist

        self.dumpScaleBarsToJson()
        # report the results
        return self.generateReport()
    
    def dumpScaleBarsToJson(self):
        result_summary = dict()
        result_summary[self.serial_id] = self.serial_id

        for bar in ScaleBars:
            # do something
            result_summary[bar.name] = bar.errorPercent()

        os.makedirs(self.output_folder, exist_ok=True)
        filename = os.path.join(self.output_folder, "{}_results.json".format(self.serial_id))
        with open(filename, "w") as filepointer:
            json.dump(result_summary, filepointer, indent=4)
        

    def takePhoto(self):
        # Set the camera viewpoint for the top-down view
        chunk = self.doc.chunks[0]
        # Save the image
        return chunk.renderPreview()

    def buildModel(self):
        chunk = self.doc.chunks[0]
        chunk.buildModel(source_data=Metashape.TiePointsData)
        chunk.reduceOverlap(overlap=30)

        chunk.buildDepthMaps(downscale=1, filter_mode=Metashape.MildFiltering)
        chunk.buildModel(source_data=Metashape.DepthMapsData)
        chunk.buildUV(page_count=2, texture_size=4096)
        chunk.buildTexture(texture_size=4096, ghosting_filter=True)
      
        img = self.takePhoto()
        img.save(os.path.join(self.output_folder, "{}_top_down.png".format(self.serial_id)))

    # dead code dont look
    def estimateImageQuality(self):
        self.chunk.analyzeImages()
       
        # create  pandas dataframe to hold the image quality stats
        quality_vals = []


        # loop through each image and get the quality stats and fill out the dataframe
        for camera in self.chunk.cameras:
            for frame in camera.frames:
                quality_vals.append(
                    {"Image": frame.photo.path, 
                    "Quality": float(frame.meta["Image/Quality"])}
                )

        # create a pandas dataframe to process the data
        quality_vals = pd.DataFrame(quality_vals)

        return quality_vals
    
    def writeAgiSoftReport(self):
        # export the agisoft report
        self.doc.chunks[0].exportReport(path=os.path.join(self.output_folder, f"{self.serial_id}_Agisoft_Report_Internal.pdf"),
                                            title=f"{self.serial_id}")


def processBarscan(validation_folder, camera_calibration_file):
    if not os.path.exists(validation_folder):
        raise Exception("Validation folder {} does not exist".format(validation_folder))

    if not os.path.exists(camera_calibration_file):
        raise Exception("Camera calibration file {} does not exist".format(camera_calibration_file))
    
    barscan = BarScanAnalizer(validation_folder, camera_calibration_file)
    barscan.align()
    barscan.filterBadPoints()
    barscan.save()
    has_passed = barscan.detectAndReportScaleBars()
    barscan.save()

    # turn this on to build a model.. but it will take an extra 10 minutes
    # barscan.buildModel()
    # barscan.save()
    barscan.writeAgiSoftReport()
   

    if has_passed:
        print("The barscan has passed for unit {}".format(barscan.serial_id))
    else:
        print("The barscan has failed for unit {}".format(barscan.serial_id))


def barscanReport():
    calib_folder = Metashape.app.getExistingDirectory("Select calibration folder (AgisoftParams)")
    data_directory = Metashape.app.getExistingDirectory("Select the Verification Data Folder Root (Voyis/Stils_XXXXXX)")
    processBarscan(data_directory, calib_folder)
   

label = "Voyis Verification/BarScanReport2.0"
Metashape.app.addMenuItem(label, barscanReport)