import cv2
import math
import copy
import numpy
import numpy as np
import warnings

def mkmat(rows, cols, L) -> numpy.ndarray:
    mat = np.array(L,dtype='float64')
    mat.resize(rows,cols)
    return mat

class PinholeCameraModel:

    """
    A pinhole camera is an idealized monocular camera.
    """

    def __init__(self):
        self._k = None
        self._d = None
        self._r = None
        self._p = None
        self._full_K = None
        self._full_P = None
        self._width = None
        self._height = None
        self._binning_x = None
        self._binning_y = None
        self._raw_roi = None
        self._tf_frame = None
        self._stamp = None
        self._resolution = None

    def from_camera_info(self, msg)->None:
        """
        :param msg: camera parameters
        :type msg:  sensor_msgs.msg.CameraInfo

        Set the camera parameters from the :class:`sensor_msgs.msg.CameraInfo` message.
        """
        self._k = mkmat(3, 3, msg.k)
        if msg.d:
            self._d = mkmat(len(msg.d), 1, msg.d)
        else:
            self._d = None
        self._r = mkmat(3, 3, msg.r)
        self._p = mkmat(3, 4, msg.p)
        self._full_K = mkmat(3, 3, msg.k)
        self._full_P = mkmat(3, 4, msg.p)
        self._width = msg.width
        self._height = msg.height
        self._binning_x = max(1, msg.binning_x)
        self._binning_y = max(1, msg.binning_y)
        self._resolution = (msg.width, msg.height)

        self._raw_roi = copy.copy(msg.roi)
        # ROI all zeros is considered the same as full resolution
        if (self._raw_roi.x_offset == 0 and self._raw_roi.y_offset == 0 and
            self._raw_roi.width == 0 and self._raw_roi.height == 0):
            self._raw_roi.width = self._width
            self._raw_roi.height = self._height
        self._tf_frame = msg.header.frame_id
        self._stamp = msg.header.stamp

        # Adjust K and P for binning and ROI
        self._k[0,0] /= self._binning_x
        self._k[1,1] /= self._binning_y
        self._k[0,2] = (self._k[0,2] - self._raw_roi.x_offset) / self._binning_x
        self._k[1,2] = (self._k[1,2] - self._raw_roi.y_offset) / self._binning_y
        self._p[0,0] /= self._binning_x
        self._p[1,1] /= self._binning_y
        self._p[0,2] = (self._p[0,2] - self._raw_roi.x_offset) / self._binning_x
        self._p[1,2] = (self._p[1,2] - self._raw_roi.y_offset) / self._binning_y

    def fromCameraInfo(self,msg)->None:
        """
        .. warning::
            PinholeCameraModel.fromCameraInfo() is deprecated. Please use from_camera_info().

        :param msg: camera parameters
        :type msg:  sensor_msgs.msg.CameraInfo
        
        Set the camera parameters from the :class:`sensor_msgs.msg.CameraInfo` message.
        """
        warnings.warn("PinholeCameraModel.fromCameraInfo() is deprecated. Please use from_camera_info()", DeprecationWarning)  
        self.from_camera_info(msg)


    def rectify_image(self, raw, rectified)->None:
        """
        :param raw:       input image
        :type raw:        :class:`CvMat` or :class:`IplImage`
        :param rectified: rectified output image
        :type rectified:  :class:`CvMat` or :class:`IplImage`

        Applies the rectification specified by camera parameters :math:`K` and and :math:`D` to image `raw` and writes the resulting image `rectified`.
        """

        self.mapx = numpy.ndarray(shape=(self._height, self._width, 1),
                           dtype='float32')
        self.mapy = numpy.ndarray(shape=(self._height, self._width, 1),
                           dtype='float32')
        cv2.initUndistortRectifyMap(self._k, self._d, self._r, self._p,
                (self._width, self._height), cv2.CV_32FC1, self.mapx, self.mapy)
        cv2.remap(raw, self.mapx, self.mapy, cv2.INTER_CUBIC, rectified)

    def rectifyImage(self, raw, rectified):
        """
        .. warning::
            PinholeCameraModel.rectifyImage() is deprecated. Please use rectify_image()

        :param raw:       input image
        :type raw:        :class:`CvMat` or :class:`IplImage`
        :param rectified: rectified output image
        :type rectified:  :class:`CvMat` or :class:`IplImage`
        
        Applies the rectification specified by camera parameters :math:`K` and and :math:`D` to image `raw` and writes the resulting image `rectified`.
        """
        warnings.warn("PinholeCameraModel.rectifyImage() is deprecated. Please use rectify_image()", DeprecationWarning) 
        self.rectify_image(raw, rectified)

    def rectify_point(self, uv_raw)->numpy.ndarray:
        """
        :param uv_raw:    pixel coordinates
        :type uv_raw:     (u, v)
        :rtype:           numpy.ndarray

        Applies the rectification specified by camera parameters
        :math:`K` and and :math:`D` to point (u, v) and returns the
        pixel coordinates of the rectified point.
        """

        src = mkmat(1, 2, list(uv_raw))
        src.resize((1,1,2))
        dst = cv2.undistortPoints(src, self._k, self._d, R=self._r, P=self._p)
        return dst[0,0]
    
    def rectifyPoint(self, uv_raw)->numpy.ndarray:
        """
        .. warning::
            PinholeCameraModel.rectifyPoint()->numpy.ndarray is deprecated. Please use rectify_point()->numpy.ndarray
        
        :param uv_raw:    pixel coordinates
        :type uv_raw:     (u, v)
        :rtype:           numpy.ndarray
        
        Applies the rectification specified by camera parameters
        :math:`K` and and :math:`D` to point (u, v) and returns the
        pixel coordinates of the rectified point.
        """
        warnings.warn("PinholeCameraModel.rectifyPoint() is deprecated. Please use rectify_point()", DeprecationWarning) 
        return self.rectify_point(uv_raw)

    def project_3d_to_pixel(self, point)->tuple[float,float]:
        """
        :param point:     3D point
        :type point:      (x, y, z)
        :rtype:           tuple[float,float]

        Returns the rectified pixel coordinates (u, v) of the 3D point,
        using the camera :math:`P` matrix.
        This is the inverse of :math:`projectPixelTo3dRay`.
        """
        src = mkmat(4, 1, [point[0], point[1], point[2], 1.0])
        dst = self._p @ src
        x = dst[0,0]
        y = dst[1,0]
        w = dst[2,0]
        if w != 0:
            return (x / w, y / w)
        else:
            return (float('nan'), float('nan'))
    
    def project3dToPixel(self, point)->tuple[float,float]:
        """
        .. warning::
            PinholeCameraModel.project3dToPixel() is deprecated. Please use project_3d_to_pixel()

        :param point:     3D point
        :type point:      (x, y, z)
        :rtype:            tuple[float,float]
        
        Returns the rectified pixel coordinates (u, v) of the 3D point,
        using the camera :math:`P` matrix.
        This is the inverse of :math:`projectPixelTo3dRay`.
        """
        warnings.warn("PinholeCameraModel.project3dToPixel() is deprecated. Please use project_3d_to_pixel()", DeprecationWarning) 
        return self.project_3d_to_pixel(point)

    def project_pixel_to_3d_ray(self, uv)->tuple[float,float,float]:
        """
        :param uv:        rectified pixel coordinates
        :type uv:         (u, v)
        :rtype:           tuple[float,float,float]

        Returns the unit vector which passes from the camera center to through rectified pixel (u, v),
        using the camera :math:`P` matrix.
        This is the inverse of :math:`project_3d_to_pixel`.
        """
        x = (uv[0] - self.cx()) / self.fx()
        y = (uv[1] - self.cy()) / self.fy()
        norm = math.sqrt(x*x + y*y + 1)
        x /= norm
        y /= norm
        z = 1.0 / norm
        return (x, y, z)

    def projectPixelTo3dRay(self, uv)->tuple[float,float,float]:
        """
        .. warning::
            PinholeCameraModel.projectPixelTo3dRay() is deprecated. Please use project_pixel_to_3d_ray()
        
        :param uv:        rectified pixel coordinates
        :type uv:         (u, v)
        :rtype:           tuple[float,float,float]

        Returns the unit vector which passes from the camera center to through rectified pixel (u, v),
        using the camera :math:`P` matrix.
        This is the inverse of :math:`project_3d_to_pixel`.
        """
        warnings.warn("PinholeCameraModel.projectPixelTo3dRay() is deprecated. Please use project_pixel_to_3d_ray()", DeprecationWarning) 
        return self.project_pixel_to_3d_ray(uv)

    def get_delta_u(self, delta_x, z)->float:
        """
        :param delta_x:         delta X, in cartesian space
        :type delta_x:          float
        :param z:               Z, in cartesian space
        :type z:                float
        :rtype:                 float

        Compute delta u, given Z and delta X in Cartesian space.
        For given Z, this is the inverse of :math:`get_delta_x`.
        """
        if z == 0:
            return float('inf')
        else:
            return self.fx() * delta_x / z

    def getDeltaU(self, deltaX, Z)->float:
        """
        .. warning::
            PinholeCameraModel.getDeltaU() is deprecated. Please use get_delta_u()
        
        :param deltaX:          delta X, in cartesian space
        :type deltaX:           float
        :param Z:               Z, in cartesian space
        :type Z:                float
        :rtype:                 float

        Compute delta u, given Z and delta X in Cartesian space.
        For given Z, this is the inverse of :math:`get_delta_x`.
        """
        warnings.warn("PinholeCameraModel.getDeltaU() is deprecated. Please use get_delta_u()", DeprecationWarning) 
        return self.get_delta_u(deltaX, Z)

    def get_delta_v(self, delta_y, z)->float:
        """
        :param delta_y:         delta Y, in cartesian space
        :type delta_y:          float
        :param z:               Z, in cartesian space
        :type z:                float
        :rtype:                 float

        Compute delta v, given Z and delta Y in Cartesian space.
        For given Z, this is the inverse of :math:`get_delta_y`.
        """
        if z == 0:
            return float('inf')
        else:
            return self.fy() * delta_y / z

    def getDeltaV(self, deltaY, Z)->float:
        """
        .. warning::
            PinholeCameraModel.getDeltaV() is deprecated. Please use get_delta_v()

        :param deltaY:          delta Y, in cartesian space
        :type deltaY:           float
        :param Z:               Z, in cartesian space
        :type Z:                float
        :rtype:                 float

        Compute delta v, given Z and delta Y in Cartesian space.
        For given Z, this is the inverse of :math:`get_delta_y`.

        PinholeCameraModel.getDeltaV() is deprecated. Please use get_delta_v()
        """
        warnings.warn("PinholeCameraModel.getDeltaV() is deprecated. Please use get_delta_v()", DeprecationWarning) 
        return(self.get_delta_v(deltaY,Z))    

    def get_delta_x(self, delta_u, z)->float:
        """
        :param deltaU:          delta u in pixels
        :type deltaU:           float
        :param Z:               Z, in cartesian space
        :type Z:                float
        :rtype:                 float

        Compute delta X, given Z in cartesian space and delta u in pixels.
        For given Z, this is the inverse of :math:`get_delta_u`.
        """
        return z * delta_u / self.fx()

    def getDeltaX(self, deltaU, Z)->float:
        """
        .. warning::
            PinholeCameraModel.getDeltaX() is deprecated. Please use get_delta_x()
        
        :param deltaU:          delta u in pixels
        :type deltaU:           float
        :param Z:               Z, in cartesian space
        :type Z:                float
        :rtype:                 float

        Compute delta X, given Z in cartesian space and delta u in pixels.
        For given Z, this is the inverse of :math:`get_delta_u`.
        """
        warnings.warn("PinholeCameraModel.getDeltaX() is deprecated. Please use get_delta_x()", DeprecationWarning)
        return self.get_delta_x(deltaU,Z)

    def get_delta_y(self, delta_v, z)->float:
        """
        :param delta_v:         delta v in pixels
        :type delta_v:          float
        :param z:               Z, in cartesian space
        :type z:                float
        :rtype:                 float

        Compute delta Y, given Z in cartesian space and delta v in pixels.
        For given Z, this is the inverse of :math:`get_delta_v`.
        """
        return z * delta_v / self.fy()

    def getDeltaY(self, deltaV, Z)->float:
        """
        .. warning::
            PinholeCameraModel.getDeltaY() is deprecated. Please use get_delta_y()

        :param deltaV:          delta v in pixels
        :type deltaV:           float
        :param Z:               Z, in cartesian space
        :type Z:                float
        :rtype:                 float

        Compute delta Y, given Z in cartesian space and delta v in pixels.
        For given Z, this is the inverse of :math:`get_delta_v`.
        """
        warnings.warn("PinholeCameraModel.getDeltaY() is deprecated. Please use get_delta_y()", DeprecationWarning)
        return self.get_delta_y(deltaV,Z)

    def full_resolution(self)->tuple[int, int]:
        """
        :rtype:                 tuple[int, int]

        Returns the full resolution of the camera as a tuple in the format (width, height)
        """
        return self._resolution

    def fullResolution(self)->tuple[int, int]:
        """
        .. warning::
            PinholeCameraModel.fullResolution() is deprecated. Please use full_resolution()
            
        :rtype:                 tuple[int, int]

        Returns the full resolution of the camera as a tuple in the format (width, height)
        """
        warnings.warn("PinholeCameraModel.fullResolution() is deprecated. Please use full_resolution()", DeprecationWarning)
        return self.full_resolution()

    def intrinsic_matrix(self)->numpy.ndarray:
        """ 
        :rtype:                 numpy.ndarray

        Returns :math:`K`, also called camera_matrix in cv docs 
        """
        return self._k
    
    def intrinsicMatrix(self)->numpy.matrix:
        """ 
        .. warning::
            PinholeCameraModel.intrinsicMatrix()->numpy.matrix is deprecated. Please use intrinsic_matrix()->numpy.ndarray
        
        :rtype:                 numpy.matrix

        Returns :math:`K`, also called camera_matrix in cv docs 
        """
        warnings.warn("PinholeCameraModel.intrinsicMatrix()->numpy.matrix is deprecated. Please use intrinsic_matrix()->numpy.ndarray", DeprecationWarning)
        return numpy.matrix(self.intrinsic_matrix(), dtype="float64")

    def distortion_coeffs(self)->numpy.ndarray:
        """ 
        :rtype:                 numpy.ndarray
        
        Returns :math:`D` 
        """
        return self._d
    
    def distortionCoeffs(self)->numpy.matrix:
        """ 
        .. warning::
            PinholeCameraModel.distortionCoeffs()->numpy.matrix is deprecated. Please use distortion_coeffs()->numpy.ndarray
        
        :rtype:                 numpy.matrix
        
        Returns :math:`D` 
        """
        warnings.warn("PinholeCameraModel.distortionCoeffs()->numpy.matrix is deprecated. Please use distortion_coeffs()->numpy.ndarray", DeprecationWarning)
        return numpy.matrix(self.distortion_coeffs(), dtype="float64")

    def rotation_matrix(self)->numpy.ndarray:
        """ 
        :rtype:                 numpy.ndarray

        Returns :math:`R` 
        """
        return self._r
    
    def rotationMatrix(self)->numpy.matrix:
        """ 
        .. warning::
            PinholeCameraModel.rotationMatrix()->numpy.matrix is deprecated. Please use rotation_matrix()->numpy.ndarray
        
        :rtype:                 numpy.matrix

        Returns :math:`R` 
        """
        warnings.warn("PinholeCameraModel.rotationMatrix()->numpy.matrix is deprecated. Please use rotation_matrix()->numpy.ndarray", DeprecationWarning)
        return np.matrix(self.rotation_matrix(), dtype='float64')

    def projection_matrix(self) ->numpy.ndarray:
        """ 
        :rtype:                 numpy.ndarray

        Returns :math:`P` 
        """
        return self._p
    
    def projectionMatrix(self) -> numpy.matrix:
        """ 
        .. warning::
            PinholeCameraModel.projectionMatrix()->numpy.matrix is deprecated. Please use projection_matrix()->numpy.ndarray
        
        :rtype:                 numpy.matrix

        Returns :math:`P` 
        """
        warnings.warn("PinholeCameraModel.projectionMatrix()->numpy.matrix is deprecated. Please use projection_matrix()->numpy.ndarray", DeprecationWarning)
        return np.matrix(self.projection_matrix(), dtype='float64')


    def full_intrinsic_matrix(self) -> numpy.ndarray:
        """ 
        :rtype:                 numpy.ndarray

        Return the original camera matrix for full resolution 
        """
        return self._full_K

    def fullIntrinsicMatrix(self) -> numpy.matrix:
        """ 
        .. warning::
            PinholeCameraModel.fullIntrinsicMatrix()->numpy.matrix is deprecated. Please use full_intrinsic_matrix()->numpy.ndarray"
        
        :rtype:                 numpy.matrix

        Return the original camera matrix for full resolution 
        """
        warnings.warn("PinholeCameraModel.fullIntrinsicMatrix()->numpy.matrix is deprecated. Please use full_intrinsic_matrix()->numpy.ndarray", DeprecationWarning)        
        return numpy.matrix(self.full_intrinsic_matrix(), dtype='float64')

    def full_projection_matrix(self)->numpy.ndarray:
        """ 
        :rtype:                 numpy.ndarray

        Return the projection matrix for full resolution """
        return self._full_P

    def fullProjectionMatrix(self)->numpy.matrix:
        """ 
        .. warning::
            PinholeCameraModel.fullProjectionMatrix()->numpy.matrix is deprecated. Please use full_projection_matrix()->numpy.ndarray
        
        :rtype:                 numpy.matrix

        Return the projection matrix for full resolution """
        warnings.warn("PinholeCameraModel.fullProjectionMatrix()->numpy.matrix is deprecated. Please use full_projection_matrix()->numpy.ndarray", DeprecationWarning)        
        return numpy.matrix(self.full_projection_matrix(), dtype='float64')
    
    def cx(self)->float:
        """ 
        :rtype:                 float      
        
        Returns x center """
        return self._p[0,2]

    def cy(self)->float:
        """ 
        :rtype:                 float      
        
        Returns y center 
        """
        return self._p[1,2]

    def fx(self)->float:
        """ 
        :rtype:                 float      
        
        Returns x focal length 
        """
        return self._p[0,0]

    def fy(self)->float:
        """ 
        :rtype:                 float      
        
        Returns y focal length 
        """
        return self._p[1,1]

    def tx(self)->float:
        """ 
        :rtype:                 float      
        
        Return the x-translation term of the projection matrix 
        """
        return self._p[0,3]

    def Tx(self)->float:
        """ 
        .. warning::
            PinholeCameraModel.Tx() is deprecated. Please use PinholeCameraModel.tx()
        
        :rtype:                 float      

        Return the x-translation term of the projection matrix 
        """
        warnings.warn("PinholeCameraModel.Tx() is deprecated. Please use PinholeCameraModel.tx()", DeprecationWarning)
        return self.tx()

    def ty(self)->float:
        """ 
        :rtype:                 float      
        
        Return the y-translation term of the projection matrix 
        """
        return self._p[1,3]

    def Ty(self)->float:
        """ 
        .. warning::
            PinholeCameraModel.Ty() is deprecated. Please use PinholeCameraModel.ty()
        
        :rtype:                 float      
        
        Return the y-translation term of the projection matrix 
        """
        warnings.warn("PinholeCameraModel.Ty() is deprecated. Please use PinholeCameraModel.ty()", DeprecationWarning)
        return self.ty()
    
    def fov_x(self)->float:
        """ 
        :rtype:                 float      
        
        Returns the horizontal field of view in radians.
        Horizontal FoV = 2 * arctan((width) / (2 * Horizontal Focal Length) )
        """
        return 2 * math.atan(self._width / (2 * self.fx()))

    def fovX(self)->float:
        """ 
        .. warning::
            PinholeCameraModel.fovX() is deprecated. Please use PinholeCameraModel.fov_x()

        :rtype:                 float      
        
        Returns the horizontal field of view in radians.
        Horizontal FoV = 2 * arctan((width) / (2 * Horizontal Focal Length) )
        """
        warnings.warn("PinholeCameraModel.fovX() is deprecated. Please use PinholeCameraModel.fov_x()", DeprecationWarning)
        return self.fov_x()

    def fov_y(self)->float:
        """ 
        :rtype:                 float      
        
        Returns the vertical field of view in radians.
        Vertical FoV = 2 * arctan((height) / (2 * Vertical Focal Length) )
        """
        return 2 * math.atan(self._height / (2 * self.fy()))

    def fovY(self)->float:
        """ 
        .. warning::
            PinholeCameraModel.fovY() is deprecated. Please use PinholeCameraModel.fov_y()
        
        :rtype:                 float      
        
        Returns the vertical field of view in radians.
        Vertical FoV = 2 * arctan((height) / (2 * Vertical Focal Length) )
        """
        warnings.warn("PinholeCameraModel.fovY() is deprecated. Please use PinholeCameraModel.fov_y()", DeprecationWarning)
        return self.fov_y()

    def tf_frame(self)->str:
        """ 
        :rtype:                 str      
        
        Returns the tf frame name - a string - of the camera.
        This is the frame of the :class:`sensor_msgs.msg.CameraInfo` message.
        """
        return self._tf_frame

    def tfFrame(self)->str:
        """ 
        .. warning::
            PinholeCameraModel.tfFrame() is deprecated. Please use PinholeCameraModel.tf_frame()

        :rtype:                 str      
        
        Returns the tf frame name - a string - of the camera.
        This is the frame of the :class:`sensor_msgs.msg.CameraInfo` message.
        """
        warnings.warn("PinholeCameraModel.tfFrame() is deprecated. Please use PinholeCameraModel.tf_frame()", DeprecationWarning)
        return self.tf_frame()

class StereoCameraModel:
    """
    An idealized stereo camera.
    """
    def __init__(self):
        self._left = PinholeCameraModel()
        self._right = PinholeCameraModel()
        self._q = None

    def from_camera_info(self, left_msg, right_msg):
        """
        :param left_msg: left camera parameters
        :type left_msg:  sensor_msgs.msg.CameraInfo
        :param right_msg: right camera parameters
        :type right_msg:  sensor_msgs.msg.CameraInfo

        Set the camera parameters from the :class:`sensor_msgs.msg.CameraInfo` messages.
        """
        self._left.from_camera_info(left_msg)
        self._right.from_camera_info(right_msg)

        # [ Fx, 0,  Cx,  Fx*-Tx ]
        # [ 0,  Fy, Cy,  0      ]
        # [ 0,  0,  1,   0      ]

        assert self._right._p is not None
        fx = self._right.projection_matrix()[0, 0]
        cx = self._right.projection_matrix()[0, 2]
        cy = self._right.projection_matrix()[1, 2]
        tx = -self._right.projection_matrix()[0, 3] / fx

        # Q is:
        #    [ 1, 0,  0, -Clx ]
        #    [ 0, 1,  0, -Cy ]
        #    [ 0, 0,  0,  Fx ]
        #    [ 0, 0, 1 / Tx, (Crx-Clx)/Tx ]

        self._q = numpy.zeros((4, 4), dtype='float64')
        self._q[0, 0] = 1.0
        self._q[0, 3] = -cx
        self._q[1, 1] = 1.0
        self._q[1, 3] = -cy
        self._q[2, 3] = fx
        self._q[3, 2] = 1 / tx

    def fromCameraInfo(self, left_msg, right_msg):
        """
        .. warning::
            StereoCameraModel.fromCameraInfo()->None is deprecated. Please use from_camera_info()->None
        
        :param left_msg: left camera parameters
        :type left_msg:  sensor_msgs.msg.CameraInfo
        :param right_msg: right camera parameters
        :type right_msg:  sensor_msgs.msg.CameraInfo

        Set the camera parameters from the :class:`sensor_msgs.msg.CameraInfo` messages.
        """

        warnings.warn("StereoCameraModel.fromCameraInfo()->None is deprecated. Please use from_camera_info()->None", DeprecationWarning)  
        self.from_camera_info(left_msg,right_msg)

    def tf_frame(self)->str:
        """ 
        :rtype:                 str      
        
        Returns the tf frame name - a string - of the camera.
        This is the frame of the :class:`sensor_msgs.msg.CameraInfo` message.
        """
        return self._left.tf_frame()

    def tfFrame(self)->str:
        """ 
        .. warning::
            StereoCameraModel.tfFrame() is deprecated. Please use tf_frame()
        
        :rtype:                 str      
        
        Returns the tf frame name - a string - of the camera.
        This is the frame of the :class:`sensor_msgs.msg.CameraInfo` message.
        """
        warnings.warn("StereoCameraModel.tfFrame() is deprecated. Please use tf_frame()", DeprecationWarning)  
        return self.tf_frame()

    def project_3d_to_pixel(self, point)->tuple[tuple[float,float],tuple[float,float]]:
        """
        :param point:     3D point
        :type point:      (x, y, z)
        :rtype:           tuple[tuple[float,float],tuple[float,float]]
        
        Returns the rectified pixel coordinates (u, v) of the 3D point, for each camera, as ((u_left, v_left), (u_right, v_right))
        using the cameras' :math:`P` matrices.
        This is the inverse of :math:`projectPixelTo3d`.
        """
        l = self._left.project_3d_to_pixel(point)
        r = self._right.project_3d_to_pixel(point)
        return (l, r)

    def project3dToPixel(self, point)->tuple[tuple[float,float],tuple[float,float]]:
        """
        .. warning::
            SteroCameraModel.project3dToPixel() is deprecated. Please use project_3d_to_pixel()

        :param point:     3D point
        :type point:      (x, y, z)
        :rtype:           tuple[tuple[float,float],tuple[float,float]]
        
        Returns the rectified pixel coordinates (u, v) of the 3D point, for each camera, as ((u_left, v_left), (u_right, v_right))
        using the cameras' :math:`P` matrices.
        This is the inverse of :math:`projectPixelTo3d`.
        """
        warnings.warn("SteroCameraModel.project3dToPixel() is deprecated. Please use project_3d_to_pixel()")
        self.project_3d_to_pixel(point)

    def project_pixel_to_3d(self, left_uv, disparity)->tuple[float,float,float]:
        """
        :param left_uv:        rectified pixel coordinates
        :type left_uv:         (u, v)
        :param disparity:      disparity, in pixels
        :type disparity:       float
        :rtype:                tuple[float,float,float] 

        Returns the 3D point (x, y, z) for the given pixel position,
        using the cameras' :math:`P` matrices.
        This is the inverse of :math:`project_3d_to_pixel`.

        Note that a disparity of zero implies that the 3D point is at infinity.
        """
        src = mkmat(4, 1, [left_uv[0], left_uv[1], disparity, 1.0])
        dst = self._q @ src
        x = dst[0, 0]
        y = dst[1, 0]
        z = dst[2, 0]
        w = dst[3, 0]
        if w != 0:
            return (x / w, y / w, z / w)
        else:
            return (0.0, 0.0, 0.0)

    def projectPixelTo3d(self, left_uv, disparity)->tuple[float,float,float]:
        """
        .. warning::
            SteroCameraModel.projectPixelTo3d() is deprecated. Please use project_pixel_to_3d()
        
        :param left_uv:        rectified pixel coordinates
        :type left_uv:         (u, v)
        :param disparity:      disparity, in pixels
        :type disparity:       float
        :rtype:                tuple[float,float,float] 

        Returns the 3D point (x, y, z) for the given pixel position,
        using the cameras' :math:`P` matrices.
        This is the inverse of :math:`project3dToPixel`.

        Note that a disparity of zero implies that the 3D point is at infinity.
        """
        warnings.warn("SteroCameraModel.projectPixelTo3d() is deprecated. Please use project_pixel_to_3d()")
        return self.project_pixel_to_3d(left_uv,disparity)

    def get_z(self, disparity)->float:
        """
        :param disparity:        disparity, in pixels
        :type disparity:         float
        :rtype:                  float

        Returns the depth at which a point is observed with a given disparity.
        This is the inverse of :math:`getDisparity`.

        Note that a disparity of zero implies Z is infinite.
        """
        if disparity == 0:
            return float('inf')
        Tx = -self._right.projection_matrix()[0, 3]
        return Tx / disparity

    def getZ(self, disparity)->float:
        """
        .. warning::
            SteroCameraModel.getZ() is deprecated. Please use get_z()
        
        :param disparity:        disparity, in pixels
        :type disparity:         float
        :rtype:                  float

        Returns the depth at which a point is observed with a given disparity.
        This is the inverse of :math:`getDisparity`.

        Note that a disparity of zero implies Z is infinite.
        """
        warnings.warn("SteroCameraModel.getZ() is deprecated. Please use get_z()")
        return self.get_z(disparity)

    def get_disparity(self, z)->float:
        """
        :param z:          Z (depth), in cartesian space
        :type z:           float
        :rtype:            float

        Returns the disparity observed for a point at depth Z.
        This is the inverse of :math:`getZ`.
        """
        if z == 0:
            return float('inf')
        tx = -self._right.projection_matrix()[0, 3]
        return tx / z

    def getDisparity(self, Z)->float:
        """
        .. warning::
            SteroCameraModel.getDisparity() is deprecated. Please use get_disparity()
        
        :param Z:          Z (depth), in cartesian space
        :type Z:           float
        :rtype:            float

        Returns the disparity observed for a point at depth Z.
        This is the inverse of :math:`getZ`.
        """
        warnings.warn("SteroCameraModel.getDisparity() is deprecated. Please use get_disparity()")
        return self.get_disparity(Z)
    
    
    def get_left_camera(self)->PinholeCameraModel:
        """ 
        :rtype: PinholeCameraModel

        Returns the PinholeCameraModel object of the left camera
        """
        return self._left
    
    def get_right_camera(self)->PinholeCameraModel:
        """ 
        :rtype: PinholeCameraModel

        Returns the PinholeCameraModel object of the right camera
        """
        return self._right