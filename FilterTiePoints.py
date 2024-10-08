import Metashape

# Checking compatibility
compatible_major_version = "2.1"
found_major_version = ".".join(Metashape.app.version.split('.')[:2])
if found_major_version != compatible_major_version:
    raise Exception("Incompatible Metashape version: {} != {}".format(found_major_version, compatible_major_version))


class TiePointCleaner():
    def __init__(self, chunk):
        self.chunk = chunk
    
    def optimize_cameras(self, chunk, calcVariance=False, adaptive_fitting=False):
        chunk.optimizeCameras(
            fit_f=True,
            fit_cx=True,
            fit_cy=True,
            fit_b1=False,
            fit_b2=False,
            fit_k1=False,
            fit_k2=False,
            fit_k3=False,
            fit_k4=False,
            fit_p1=True,
            fit_p2=True,
            fit_corrections=False,
            adaptive_fitting=adaptive_fitting,
            tiepoint_covariance=calcVariance,
    )

    def filterBadPoints(self, 
                        img_count=2, 
                        max_reconstruction_uncertainty=35, 
                        min_projection_accuracy=15, 
                        min_reprojection_error=0.4):
        
        print("filtering points with less then {} observations".format(img_count))
        # remove points with less than 3 observations
        chunk = self.chunk
        # filter out bad points by removing points that only have 2 or less observations
        f = Metashape.TiePoints.Filter()
        f.init(chunk, criterion=Metashape.TiePoints.Filter.ImageCount)
        f.selectPoints(img_count)
        f.removePoints(img_count)

        self.optimize_cameras(chunk, adaptive_fitting=False)

        #remove points with high reconstruction uncertainty
        print("filtering points with high reconstruction uncertainty higher then {}".format(max_reconstruction_uncertainty))

        for reconstruction_uncertainty in range(100, max_reconstruction_uncertainty, -10):
            f = Metashape.TiePoints.Filter()
            f.init(
                chunk,
                criterion=Metashape.TiePoints.Filter.ReconstructionUncertainty,
            )
            f.removePoints(reconstruction_uncertainty)
            self.optimize_cameras(chunk)

        # remove points with low projection Accuracyy
        print("filtering with projection uncertainty higher then {}".format(min_projection_accuracy))
        for projection_accuracy in range(90, min_projection_accuracy, -10):
            f = Metashape.TiePoints.Filter()
            f.init(chunk, criterion=Metashape.TiePoints.Filter.ProjectionAccuracy)
            f.removePoints(projection_accuracy)
            self.optimize_cameras(chunk)

        print("filtering points with reprojection error higher then {}".format(min_reprojection_error))
        for reprojection_error_int in range(12, min_reprojection_error * 10, -1):
            f = Metashape.TiePoints.Filter()
            f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
            reprojection_error = float(reprojection_error_int) / 10
            f.removePoints(reprojection_error)
            self.optimize_cameras(chunk)

        # one last calc with the variance for saving
        self.optimize_cameras(chunk, calcVariance=True, adaptive_fitting=False)

    # def filterImageQuality(self, threshold=0.5):
    #     self.chunk.analyzeImages()
    
    #     # # createa  pandas dataframe to hold the image quality stats
    #     # quality_vals = []

    #     # loop through each image and get the quality stats and fill out the dataframe
    #     for camera in self.chunk.cameras:
    #         for frame in camera.frames:
    #             quality = float(frame.meta['Image/Quality'])
    #             if quality < threshold or quality > 1.2:
    #                 print("poor image detected: {}".format(camera.photo.path))
    #                 camera.enabled = False
        

def cleanTiePoints():
    chunk = Metashape.app.document.chunk
    if chunk is None:
        raise Exception("Empty project!")
    
    cleaner = TiePointCleaner(chunk)
    cleaner.filterBadPoints()
    print("Tie points cleaned")
    return True


label = "Voyis/Filter Tie Points"
Metashape.app.addMenuItem(label, cleanTiePoints)