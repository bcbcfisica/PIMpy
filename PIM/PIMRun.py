import rebound
import folium
import msise00
import datetime
from datetime import datetime, timedelta
from datetime import datetime
import pandas as pd
import numpy as np
from numpy import sin,cos,sqrt
from pyproj import Transformer
from PyAstronomy import pyasl
import os
import math
import sympy as sym
import variablesPIM
import validationPIM
from typing import Tuple
import multiprocessing


def convEqToHor(y, m, d, ho, mi, se, alt, lon, lat, ra, dec):
    '''
    Converts equatorial coordinates to horizontal coordinates, returning the azimuth and altitude.

    Args:
        y (int): Year.
        m (int): Month.
        d (int): Day.
        ho (int): Hour.
        mi (int): Minute.
        se (int): Second.
        alt (float): Altitude of the observer in meters.
        lon (float): Longitude of the observer in degrees.
        lat (float): Latitude of the observer in degrees.
        ra (float): Right ascension of the object in degrees.
        dec (float): Declination of the object in degrees.

    Returns:
        tuple: A tuple containing the azimuth (in degrees) and altitude (in degrees) of the object.
    '''
    jd = datetime.datetime(y, m, d, ho, mi, se)
    jds = pyasl.jdcnv(jd)  # Convert from Gregorian to Julian calendar
    alt, az, ha = pyasl.eq2hor(jds, ra, dec, lon=lon, lat=lat, alt=alt)
    return az[0], alt[0]

def sphToCartGeo(RTP):
    '''
    Converts spherical coordinates to geographic coordinates.

    Args:
        RTP (tuple): A tuple containing the radial distance (in km), polar angle (in radians), and azimuthal angle (in radians).

    Returns:
        np.ndarray: A 1D numpy array with the x, y, and z coordinates (in km) in the geographic coordinate system.
    '''
    rc = RTP[0] * 1000
    lonc = np.rad2deg(RTP[1])
    latc = np.rad2deg(RTP[2])
    trans_proj_geo = Transformer.from_crs("lla", {"proj": 'geocent', "ellps": 'WGS84', "datum": 'WGS84'})
    xc, yc, zc = trans_proj_geo.transform(latc, lonc, rc)
    return np.array([xc, yc, zc]) / 1000

def sphToCart(RTP):
    '''
    Converts spherical coordinates to Cartesian coordinates.

    Args:
        RTP (tuple): A tuple containing the radial distance (in km), polar angle (in radians), and azimuthal angle (in radians).

    Returns:
        np.ndarray: A 1D numpy array with the x, y, and z coordinates (in km) in the Cartesian coordinate system.
    '''
    xc = RTP[0] * np.cos(RTP[2]) * np.cos(RTP[1])
    yc = RTP[0] * np.cos(RTP[2]) * np.sin(RTP[1])
    zc = RTP[0] * np.sin(RTP[2])
    return np.array([xc, yc, zc])

def carttoSphGeo(XYZ):
    '''
    Converts Cartesian coordinates to geographic coordinates.

    Args:
        XYZ (np.ndarray): A 1D numpy array with the x, y, and z coordinates (in km) in the Cartesian coordinate system.

    Returns:
        np.ndarray: A 1D numpy array with the radial distance (in km), polar angle (in radians), and azimuthal angle (in radians) in the geographic coordinate system.
    '''
    transprojCart = Transformer.from_crs({"proj":'geocent',"datum":'WGS84',"ellps":'WGS84'},"lla")
    XYZc = XYZ * 1000
    lat, lon, alt = transprojCart.transform(XYZc[0], XYZc[1], XYZc[2])
    return np.array([alt/1000, np.radians(lon), np.radians(lat)])

def carttoSph(XYZ):
    '''
    Converts Cartesian coordinates to spherical coordinates.

    Args:
        XYZ (np.ndarray): A 1D numpy array with the x, y, and z coordinates (in km) in the Cartesian coordinate system.

    Returns:
        np.ndarray: A 1D numpy array with the spherical coordinates (radius, polar angle, azimuthal angle) in radians.
    '''
    r = sqrt(XYZ[0]**2 + XYZ[1]**2 + XYZ[2]**2)
    theta = np.arctan2(XYZ[1], XYZ[0])
    phi = np.arctan2(XYZ[2], sqrt(XYZ[0]**2 + XYZ[1]**2))
    return np.array([r, theta, phi])

def translation(A, B):
    '''
    Performs vector addition.

    Args:
        A (np.ndarray): A 1D numpy array with the coordinates of vector A.
        B (np.ndarray): A 1D numpy array with the coordinates of vector B.

    Returns:
        np.ndarray: A 1D numpy array with the coordinates of the resulting vector.
    '''
    return (A + B)

def distMet(P1, P2):
    '''
    Calculates the Euclidean distance between two points in spherical coordinates.

    Args:
        P1 (np.ndarray): A 1D numpy array containing the spherical coordinates of the first point (radius, longitude, latitude).
        P2 (np.ndarray): A 1D numpy array containing the spherical coordinates of the second point (radius, longitude, latitude).

    Returns:
        float: The Euclidean distance between the two points.
    '''
    P1d = np.copy(P1)
    P2d = np.copy(P2)
    
    # Convertendo ângulos de graus para radianos
    for i in range(1,3):
        P1d[i] = np.radians(P1d[i])
        P2d[i] = np.radians(P2d[i])
    
    # Convertendo coordenadas esféricas para cartesianas geocêntricas
    cartP1 = sphToCartGeo(P1d)
    cartP2 = sphToCartGeo(P2d)
    
    # Calculando a distância euclidiana entre as posições
    return np.linalg.norm(cartP1-cartP2)

def velMet(P1v,P2v,time): 
    '''
    Calculates the velocity of a meteor from its initial and final positions and the time between these positions.

    Args:
        P1v (np.ndarray): A 1D numpy array containing the initial position of the meteor in spherical coordinates (radius, azimuth, elevation).
        P2v (np.ndarray): A 1D numpy array containing the final position of the meteor in spherical coordinates (radius, azimuth, elevation).
        time (float): The time (in seconds) between the two positions.

    Returns:
        float: The velocity (in km/s) of the meteor.
    '''
    return distMet(P1v,P2v)/time

def coordGeo(m, sta):
    '''
    Determines the line of the meteor in geocentric coordinates.

    Args:
        m (tuple): A tuple of three floats containing the meteor's apparent position in spherical coordinates (azimuth, elevation, distance).
        sta (tuple): A tuple of three floats containing the station's geodetic coordinates in degrees (longitude, latitude, altitude).

    Returns:
        np.ndarray: A 1D numpy array with the geocentric coordinates of the meteor's line.
    '''    
    # Check input arguments
    if not isinstance(m, tuple) or len(m) != 3 or not isinstance(sta, tuple) or len(sta) != 3:
        raise ValueError("Input arguments must be tuples of three floats.")
    if not all(isinstance(coord, (int, float)) for tup in (m, sta) for coord in tup):
        raise ValueError("All coordinates must be numeric.")
    if not -180 <= sta[0] <= 180 or not -90 <= sta[1] <= 90 or not sta[2] >= 0:
        raise ValueError("Invalid station coordinates.")
    if not 0 <= m[0] < 360 or not -90 <= m[1] <= 90 or not m[2] >= 0:
        raise ValueError("Invalid meteor coordinates.")
    
    # Define symbols
    rCam, xM, yM, zM = sym.symbols('rCam xM yM zM')
    
    # Convert meteor's apparent position to Cartesian coordinates
    mCL = sphToCart(m)
    
    # Apply rotations to convert to geocentric coordinates
    mCG = sym.rot_axis2(np.pi/2 - sta[2])@(mCL)
    mCG = sym.rot_axis3(sta[1])@(mCG)
    mCG = np.array([-mCG[0], mCG[1], mCG[2]])
    
    # Translate to station coordinates
    staCL = sphToCartGeo(sta)
    mCG = translation(mCG, staCL)
    
    return mCG

def detPlan(sta, mA, mB):
    '''
    Determines the equation of the plane defined by the station and two meteors' coordinates.

    Args:
        sta (tuple): A tuple containing the station's coordinates in spherical coordinates (latitude, longitude, altitude).
        mA (np.ndarray): A 1D numpy array containing the spherical coordinates of the first meteor (azimuth, zenith, distance).
        mB (np.ndarray): A 1D numpy array containing the spherical coordinates of the second meteor (azimuth, zenith, distance).

    Returns:
        sympy.Expr: The equation of the plane defined by the station and the two meteors.
    '''
    # Convert station coordinates to Cartesian coordinates
    staCL = sphToCartGeo(sta)
    
    # Convert meteor coordinates to Cartesian coordinates
    mAG = coordGeo(mA, sta)
    mBG = coordGeo(mB, sta)

    # Calculate the normal vector of the plane defined by the station and the two meteors
    planM = np.cross((mAG-staCL),(mBG-staCL))
    
    # Define the equation of the plane in terms of its normal vector and a point on the plane
    xM, yM, zM = sym.symbols('xM yM zM')
    mM = np.array([xM,yM,zM])
    planMn = np.dot(planM, mM)
    d = -1. * planMn.subs([(xM, staCL[0]), (yM, staCL[1]), (zM, staCL[2])])
    
    return planMn + d

def point(sta,sol,m100):
    '''
    Finds the intersection points between the planes of each camera and returns the points of each camera on the meteor.

    Args:
        sta (tuple): A tuple containing the geographical coordinates of the station (latitude, longitude, altitude).
        sol (sympy expression): The equation of the meteor's line.
        m100 (np.ndarray): The position vector of the meteor in the horizontal coordinate system (100 km).

    Returns:
        tuple: A tuple containing the geographical coordinates of the intersection point between the planes of each camera and the meteor's line.
    '''
    rCam,xM,yM,zM = sym.symbols('rCam xM yM zM')
    mCam = np.array([rCam,m100[1],m100[2]])
    mCamG = coordGeo(mCam,sta)
    f=mCamG[1]-(sol[yM].subs(zM,mCamG[2]))
    rF = sym.solve(f,rCam)
    x = mCamG[0].subs(rCam,rF[0])
    y = mCamG[1].subs(rCam,rF[0])
    z = mCamG[2].subs(rCam,rF[0])
    vF1 = np.array([x,y,z])
    vF1G = carttoSphGeo(vF1)
    vF1G[1] = np.rad2deg(vF1G[1])
    vF1G[2] = np.rad2deg(vF1G[2])
    return vF1G
    
def meteorDataG(alt1, lon1, lat1, alt2, lon2, lat2, az1A, h1A, az2A, h2A, az1B, h1B, az2B, h2B):
    '''
    Determines the coordinates of the intersection points between the planes of each camera and the meteor's line.

    Args:
        alt1 (float): Altitude of station 1 in meters.
        lon1 (float): Longitude of station 1 in degrees.
        lat1 (float): Latitude of station 1 in degrees.
        alt2 (float): Altitude of station 2 in meters.
        lon2 (float): Longitude of station 2 in degrees.
        lat2 (float): Latitude of station 2 in degrees.
        az1A (float): Azimuth of meteor 1 observed from camera A in degrees.
        h1A (float): Zenith angle of meteor 1 observed from camera A in degrees.
        az2A (float): Azimuth of meteor 2 observed from camera A in degrees.
    '''
    sta1 = np.array([alt1,np.radians(lon1),np.radians(lat1)])
    sta2 = np.array([alt2,np.radians(lon2),np.radians(lat2)])
    m1A100 = np.array([100.,np.radians(az1A),np.radians(h1A)])
    m2A100 = np.array([100.,np.radians(az2A),np.radians(h2A)])
    m1B100 = np.array([100.,np.radians(az1B),np.radians(h1B)])
    m2B100 = np.array([100.,np.radians(az2B),np.radians(h2B)])
    xM, yM, zM = sym.symbols('xM yM zM')
    plano1 = detPlan(sta1,m1A100,m1B100)
    plano2 = detPlan(sta2,m2A100,m2B100)
    sol = sym.solve([plano1,plano2],(xM,yM,zM))
    v1Acam =  point(sta1, sol, m1A100)
    v1Bcam =  point(sta1, sol, m1B100)
    v2Acam =  point(sta2, sol, m2A100)
    v2Bcam =  point(sta2, sol, m2B100)
    return {'v1Acam' : v1Acam,'v1Bcam' : v1Bcam,'v2Acam' : v2Acam,'v2Bcam' : v2Bcam}

def readInputFile (file_path):
    '''
    Read the input file with meteor parameters.

    Args:
        file_path (str): Path to the input file.

    Returns:
        tuple: A tuple with the following elements:
            - str: Path to the input file.
            - pd.DataFrame: A pandas DataFrame with the meteor parameters.
            - list: A list with the meteor date and time [year, month, day, hour, minute, second].
            - str: The name of the meteor and the directory for calculation.
    '''
    full_path = variablesPIM.directorystr + file_path
    df = pd.read_csv(full_path, sep='=', comment='#', index_col=0).transpose()
    df = df.apply(pd.to_numeric, errors='ignore')
    date_time = [df['ano'][0], df['mes'][0], df['dia'][0], df['hora'][0], df['minuto'][0], df['segundo'][0]]
    df['massaPont'] = df['massaPont'].astype(str)
    meteor_name = str(df['meteorN'][0])

    return full_path, df, date_time, meteor_name 

def pointsIntervalsCase1(readout):
    '''
    Calculate points and intervals for Case 1.

    Args:
        readout (pd.DataFrame): A pandas DataFrame with meteor parameters.

    Returns:
        tuple: A tuple containing latitude, longitude, altitude, deltaT for the two points.
    '''
    P1lat = readout['P1lat'][0]
    P1lon = readout['P1lon'][0]
    P1alt =  readout['P1alt'][0]
    P2lat =  readout['P2lat'][0]
    P2lon = readout['P2lon'][0]
    P2alt = readout['P2alt'][0]
    deltaT = readout['deltaT'][0]

    return P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT

def pointsIntervalsCase2(readout,meteorPoints):
    '''
    Calculate points and intervals for Case 2.

    Args:
        readout (pd.DataFrame): A pandas DataFrame with meteor parameters.
        meteorPoints (dict): A dictionary containing meteor points.

    Returns:
        tuple: A tuple containing latitude, longitude, altitude, deltaT for the two points.
    '''
    if readout['cam'][0] == 1:

        P1alt,P1lon,P1lat = meteorPoints['v1Acam'][0],meteorPoints['v1Acam'][1],meteorPoints['v1Acam'][2]
        P2alt,P2lon,P2lat = meteorPoints['v1Bcam'][0],meteorPoints['v1Bcam'][1],meteorPoints['v1Bcam']  [2]
        deltaT = readout['deltaT1'][0]

    else:

        P1alt,P1lon,P1lat = meteorPoints['v2Acam'][0],meteorPoints['v2Acam'][1],meteorPoints['v2Acam'][2]
        P2alt,P2lon,P2lat = meteorPoints['v2Bcam'][0],meteorPoints['v2Bcam'][1],meteorPoints['v2Bcam'][2]
        deltaT = readout['deltaT2'][0]

    return P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT

def pointsIntervalsCase3(readout, dataMeteoro,meteorPoints):
    '''
    Calculate points and intervals for Case 3.

    Args:
        readout (pd.DataFrame): A pandas DataFrame with meteor parameters.
        dataMeteoro (list): A list with meteor date and time [year, month, day, hour, minute, second].
        meteorPoints (dict): A dictionary containing meteor points.

    Returns:
        tuple: A tuple containing latitude, longitude, altitude, deltaT for the two points.
    '''
    if readout['cam'][0] == 1:

        P1alt,P1lon,P1lat = meteorPoints['v1Acam'][0],meteorPoints['v1Acam'][1],meteorPoints['v1Acam'][2]
        P2alt,P2lon,P2lat = meteorPoints['v1Bcam'][0],meteorPoints['v1Bcam'][1],meteorPoints['v1Bcam']  [2]
        deltaT = readout['deltaT1'][0]


    else:

        P1alt,P1lon,P1lat = meteorPoints['v2Acam'][0],meteorPoints['v2Acam'][1],meteorPoints['v2Acam'][2]
        P2alt,P2lon,P2lat = meteorPoints['v2Bcam'][0],meteorPoints['v2Bcam'][1],meteorPoints['v2Bcam'][2]
        deltaT = readout['deltaT2'][0]

    return P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT

def pointsIntervalsCase0(readout):
    '''
    Calculate points and intervals for Case 0.

    Args:
        readout (pd.DataFrame): A pandas DataFrame with meteor parameters.

    Returns:
        tuple: A tuple containing latitude, longitude, altitude, deltaT, Vx, Vy, Vz for the two points.
    '''
    P1alt,P1lon,P1lat = readout['alt4d'][0],readout['lon4d'][0],readout['lat4d'][0]
    P2alt,P2lon,P2lat = P1alt,P1lon,P1lat
    Vx4,Vy4,Vz4= readout['Vx4d'][0]*1000.,readout['Vy4d'][0]*1000.,readout['Vz4d'][0]*1000.
    deltaT=0
    return P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT, Vx4, Vy4, Vz4
    
def meteorPoints (readout,dataMeteoro):
    '''
    Calculate meteor points based on input parameters.

    Args:
        readout (pd.DataFrame): A pandas DataFrame with meteor parameters.
        dataMeteoro (list): A list with meteor date and time [year, month, day, hour, minute, second].

    Returns:
        dict: A dictionary containing meteor points.
    '''
    alt1,lon1,lat1 = readout['alt1'][0],readout['lon1'][0],readout['lat1'][0]
    alt2,lon2,lat2 = readout['alt2'][0],readout['lon2'][0],readout['lat2'][0]
    ra1Ini, dec1Ini =  readout['ra1Ini'][0],readout['dec1Ini'][0]
    ra2Ini, dec2Ini =  readout['ra2Ini'][0],readout['dec2Ini'][0]
    ra1Fin, dec1Fin =  readout['ra1Fin'][0],readout['dec1Fin'][0]
    ra2Fin, dec2Fin =  readout['ra2Fin'][0],readout['dec2Fin'][0]
    y, m, d, ho, mi, se = dataMeteoro[0],dataMeteoro[1],dataMeteoro[2],dataMeteoro[3],dataMeteoro[4],dataMeteoro[5]
    az1Ini, h1Ini = convEqToHor(y, m, d, ho, mi, se, alt1, lon1, lat1, ra1Ini, dec1Ini)
    az2Ini, h2Ini = convEqToHor(y, m, d, ho, mi, se, alt2, lon2, lat2, ra2Ini, dec2Ini)
    az1Fin, h1Fin = convEqToHor(y, m, d, ho, mi, se, alt1, lon1, lat1, ra1Fin, dec1Fin)
    az2Fin, h2Fin = convEqToHor(y, m, d, ho, mi, se, alt2, lon2, lat2, ra2Fin, dec2Fin)

    meteorPoints = (meteorDataG(alt1, lon1, lat1, alt2, lon2, lat2, 
                                az1Ini, h1Ini, az2Ini, h2Ini, az1Fin, h1Fin, az2Fin, h2Fin))
    return meteorPoints

def massPoint (readout):
    '''
    Parse and extract mass point information from the input DataFrame.

    Args:
        readout (pd.DataFrame): A pandas DataFrame with meteor parameters.

    Returns:
        list: A list of mass points.
    '''
    massaPont = []
    if readout['massaPont'][0].find(',') == -1:
        massaPont.append(float(readout['massaPont'][0]))

    else:
        massaPontString= readout['massaPont'][0].split(sep=',')
        for i in massaPontString:
            massaPont.append(float(i))
    return massaPont

def writeData (readout, meteorN,P1lat,P1lon,P1alt,P2lat,P2lon,P2alt,Vx4,Vy4,Vz4,deltaT,horaMeteoro ):
    '''
    Write calculated data to an output file.

    Args:
        readout (pd.DataFrame): A pandas DataFrame with meteor parameters.
        meteorN (str): Name of the meteor.
        P1lat (float): Latitude of point 1.
        P1lon (float): Longitude of point 1.
        P1alt (float): Altitude of point 1.
        P2lat (float): Latitude of point 2.
        P2lon (float): Longitude of point 2.
        P2alt (float): Altitude of point 2.
        Vx4 (float): Velocity along X-axis.
        Vy4 (float): Velocity along Y-axis.
        Vz4 (float): Velocity along Z-axis.
        deltaT (float): Time interval.
        horaMeteoro (datetime): Meteor date and time.
    '''
    gravarEntrada = open((variablesPIM.directorystr+'/data.txt'),'w')
    gravarEntrada.write(("Meteor: "+meteorN+'\n \n'))
    linha='P1: lat: '+str(P1lat)+'  lon: '+str(P1lon)+'  alt: '+str(P1alt) +'\n'
    gravarEntrada.write(linha)

    if readout['opcao'][0] != 4:
        linha='P2: lat: '+ str(P2lat)+'  lon: '+ str(P2lon)+'  alt: '+str(P2alt) +'\n'
        gravarEntrada.write(linha)

    else:
        linha='Vx (km/s): '+str(Vx4/1000)+'   Vy (km/s): '+str(Vy4/1000)+'  Vz (km/s): '+str(Vz4/1000) +'\n'
        gravarEntrada.write(linha)

    linha='time: '+str(deltaT)+' \n'
    gravarEntrada.write(linha)
    linha='date: '+horaMeteoro.strftime("%Y-%m-%d %H:%M:%S")+'\n'
    gravarEntrada.write(linha)
    gravarEntrada.close()

    
def PIMRun(arquivoMeteoroEntrada):


# readout arquivo entrada

    arquivo, readout, dataMeteoro, meteorN = readInputFile(arquivoMeteoroEntrada)

###############################################################################################
# Pontos e Intervalo entre os pontos

    meteorPoints = meteorPoints (readout,dataMeteoro)

    if readout['opcao'][0] == 1:
        P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT= pointsIntervalsCase1(readout)

    elif readout['opcao'][0] == 2:
        P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT = pointsIntervalsCase2(readout,meteorPoints)
        
    elif readout['opcao'][0] == 3:
        P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT = pointsIntervalsCase3(readout, dataMeteoro,meteorPoints)

    else:
        P1lat, P1lon, P1alt, P2lat, P2lon, P2alt, deltaT, Vx4, Vy4, Vz4 = pointsIntervalsCase0(readout)

#################################################################################################

    
    horaMeteoro = datetime(dataMeteoro[0],dataMeteoro[1],dataMeteoro[2],     
                         dataMeteoro[3],dataMeteoro[4],dataMeteoro[5])      # Meteor Timestamp (year, month, day, hour, minute, second)
    
    massaPont = massPoint (readout)             # Masses for impact points kg [0.001, 0.01, 0.1, 1, 10, 50, 100, 150]
    CD=readout['CD'][0]
    densMeteor = readout['densMeteor'][0]       # Density
    massaInt = readout['massaInt'][0]           # Meteor mass
    tInt = readout['tInt'][0]                   # Integration time (days)
    tIntStep = readout['tIntStep'][0]           # Integration step
    tamHill=readout['tamHill'][0]               # Hill sphere size for close encounter

    ###############################################################################################
    # Directory Creation

    meteorN = meteorN + " - Analyses"
    validationPIM.createDirIfDoesntExist(variablesPIM.directorystr, meteorN)

    ###############################################################################################

    # Record general information
    
    writeData (readout, meteorN,P1lat,P1lon,P1alt,P2lat,P2lon,P2alt,Vx4,Vy4,Vz4,deltaT,horaMeteoro)

    ###############################################################################################

    # Consolidating Data    
    
    P1 = np.array([P1alt, P1lon, P1lat])
    P2 = np.array([P2alt, P2lon, P2lat])
    deltaT = readout['deltaT'][0]
    distance = distMet(P1,P2)
    velocity = velMet(P1,P2,deltaT)
    distStations = distMet(np.array([meteorPoints[0], meteorPoints[1], meteorPoints[2]]),np.array([meteorPoints[3], meteorPoints[4], meteorPoints[5]]))
    legthCam1 = distMet(meteorPoints['v1Acam'],meteorPoints['v1Bcam'])
    legthCam2 = distMet(meteorPoints['v2Acam'],meteorPoints['v2Bcam'])
    speedCam1 = velMet(meteorPoints['v1Acam'],meteorPoints['v1Bcam'],readout['deltaT1'][0])
    speedCam2 = velMet(meteorPoints['v2Acam'],meteorPoints['v2Bcam'],readout['deltaT2'][0])
    initialDistance = distMet(meteorPoints['v2Acam'],meteorPoints['v1Acam'])
    finalDistance = distMet(meteorPoints['v2Bcam'],meteorPoints['v1Bcam'])
    velocityOp4 = str(sqrt(Vx4**2+Vy4**2+Vz4**2)/1000.)
    
    
    ###############################################################################################

    # Write Data

    if readout['opcao'][0] == 1:
        strPontosCam = f'Meteor Length (km):\n{distance}  \n--------------\n'
        strPontosCam += f'Meteor Speed (km/s):\n{velocity}\n--------------\n'
        with open(variablesPIM.directorystr+ '/'+'data.txt',"a") as filesCam:
            filesCam.write(strPontosCam)
        if ( velocity < 11.):
            with open(variablesPIM.directorystr+ '/'+'data.txt',"a") as filesCam:
                filesCam.write("Slow velocity")


    if readout['opcao'][0] == 2 or readout['opcao'][0] == 3:
        
        strPontosCam =  str(meteorPoints) + '\n' + '--------------\n'
        strPontosCam += f'Distance between stations: \n{distStations}\n--------------\n'
        strPontosCam += f'Meteor cam1 Length (km):   \n{legthCam1}   \n--------------\n'
        strPontosCam += f'Meteor cam2 Length (km):   \n{legthCam2}   \n--------------\n'
        strPontosCam += f'Meteor cam1 Speed (km/s):  \n{speedCam1}   \n--------------\n'
        strPontosCam += f'Meteor cam2 Speed (km/s):  \n{speedCam2}   \n--------------\n'
        strPontosCam += "\n-----Distance Points A B between cameras-------\n"
        strPontosCam += f'Initial distance of the meteor between the cameras (km): \n{initialDistance}\n--------------\n'
        strPontosCam += f'Final distance of the meteor between the cameras (km): \n{finalDistance}    \n--------------\n'
        
        with open(variablesPIM.directorystr+ '/'+'data.txt',"a") as filesCam:
            filesCam.write(strPontosCam)
            filesCam.write("\n using cam = " + str(readout['cam'][0])+ '\n')
        if (readout['cam'][0] == 1):
            if (velMet(meteorPoints['v1Acam'],meteorPoints['v1Bcam'],readout['deltaT1'][0]) < 11.):
                with open(variablesPIM.directorystr+ '/'+'data.txt',"a") as filesCam:
                    filesCam.write("slow velocity")
            return
        elif (readout['cam'][0] == 2):
            if (velMet(meteorPoints['v2Acam'],meteorPoints['v2Bcam'],readout['deltaT2'][0]) < 11.):
                with open(variablesPIM.directorystr+ '/'+'data.txt',"a") as filesCam:
                    filesCam.write("slow velocity")
                return


    if readout['opcao'][0] == 4:
        strPontosCam =f'Meteor Speed (km/s):\n{velocityOp4}\n--------------\n'
        with open(variablesPIM.directorystr+ '/'+'data.txt',"a") as filesCam:
            filesCam.write(strPontosCam)
        if (velocityOp4<11.):
            with open(variablesPIM.directorystr+ '/'+'data.txt',"a") as filesCam:
                filesCam.write("slow velocity")

    print(strPontosCam)

    ###############################################################################################

    # Initial meteor data in geocentric coordinates
    # Create lists according to the number of masses to be integrated

    transprojCart = Transformer.from_crs({"proj":'geocent',"datum":'WGS84',"ellps":'WGS84'},"lla")  
    transprojGeo = Transformer.from_crs("lla",{"proj":'geocent',"ellps":'WGS84',"datum":'WGS84'})

    A = []
    for i in massaPont:                         # Determine the masses to be run
        v = i/densMeteor                        # Define the volume (mass/density)
        r = (v*3./(4.*math.pi))**(1./3.)/100.   # Define the radius
        A.append(math.pi*r*r)

    # Initial conditions of the meteor, position, and velocity    
    X1 = [None] * len(massaPont)
    Y1 = [None] * len(massaPont)
    Z1 = [None] * len(massaPont)
    X2 = [None] * len(massaPont)
    Y2 = [None] * len(massaPont)
    Z2 = [None] * len(massaPont)
    Vx1= [None] * len(massaPont)
    Vy1= [None] * len(massaPont)
    Vz1 = [None] * len(massaPont)
    altM = [None] * len(massaPont)
    latM = [None] * len(massaPont)
    lonM = [None] * len(massaPont)
    altM2 = [None] * len(massaPont)
    latM2 = [None] * len(massaPont)
    lonM2 = [None] * len(massaPont)

    particulas = [None] * len(massaPont)

    for i in range (len(massaPont)):
        X1[i],Y1[i],Z1[i] = transprojGeo.transform(P1lat,P1lon,P1alt*1000.)
        X2[i],Y2[i],Z2[i] = transprojGeo.transform(P2lat,P2lon,P2alt*1000.)
        if readout['opcao'][0] == 4:
            Vx1[i] = Vx4
            Vy1[i] = Vy4
            Vz1[i] = Vz4
        else:
            Vx1[i] = (X2[i]-X1[i])/deltaT
            Vy1[i] = (Y2[i]-Y1[i])/deltaT
            Vz1[i] = (Z2[i]-Z1[i])/deltaT
        particulas[i]=i
        
    X = [None] * len(massaPont)
    Y = [None] * len(massaPont)
    Z = [None] * len(massaPont)
    Vx= [None] * len(massaPont)
    Vy= [None] * len(massaPont)
    Vz= [None] * len(massaPont)

    ###############################################################################################

    #integraçao pra frente
    # Integração dos pontos de queda (dados salvos em arquivos .out)
    # (este procedimento é demorado devido ao arrasto atmosférico)


    #particulas=[0]
    #while len(particulas)!=0:

    for i in range (len(massaPont)):
        X[i],Y[i],Z[i]=(X1[i]+X2[i])/2,(Y1[i]+Y2[i])/2,(Z1[i]+Z2[i])/2
        Vx[i],Vy[i],Vz[i]=Vx1[i],Vy1[i],Vz1[i]
        latM[i],lonM[i],altM[i] = transprojCart.transform(X[i],Y[i],Z[i])

    arquivo=open((variablesPIM.directorystr+'/saida.out'),'w')
    arquivoQueda=open((variablesPIM.directorystr+'/queda.dat'),'w')
    arquivoQueda.write("time(s) vel alt(km) lon lat \n")

    for j in range (len(massaPont)):
        tempo=0
        passo=5
        ASection=A[j]
        massaParticula=massaPont[j]

        while altM[j]>0.:
            os.system('clear')
            Vm=np.sqrt(Vx[j]**2+Vy[j]**2+Vz[j]**2)
            if (((altM[j]/1000)<0.005)):
                passo=0.1/Vm
            elif (((altM[j]/1000)<0.040)):
                passo=2/Vm
            elif (((altM[j]/1000)<0.150)):
                passo=20/Vm
            elif (((altM[j]/1000)<0.2)):
                passo=50/Vm
            elif (((altM[j]/1000)<0.4)):
                passo=100/Vm            
            elif (((altM[j]/1000)<1)):
                passo=200/Vm
            elif (((altM[j]/1000)<3)):
                passo=500/Vm
            elif ((altM[j]/1000)<5):
                passo=1000/Vm
            else:
                passo=2000/Vm
            
            print(tempo,"massa(kg): ",massaPont[j],"altura atual (km): ",altM[j]/1000.)
            arquivoQueda.write(str(str(tempo)+" "+str(Vm)+" "+str(altM[j]/1000)+" "+str(lonM[j])+" "+str(latM[j])+" \n"))
            sim = rebound.Simulation()
            sim.integrator = "ias15"
            #sim.ri_ias15.epsilon=1e-3
            sim.units = ('m', 's', 'kg')
            sim.add(m=5.97219e24,hash='earth')
            meteor = rebound.Particle(m=massaPont[j],x=X[j],y=Y[j],z=Z[j],vx=Vx[j],vy=Vy[j],vz=Vz[j])
            sim.add(meteor)
            #sim.status()
            ps=sim.particles
            atmos = msise00.run(time=datetime(horaMeteoro.year,horaMeteoro.month,horaMeteoro.day,horaMeteoro.hour,horaMeteoro.minute,horaMeteoro.second), altkm=altM[j]/1000., glat=latM[j], glon=lonM[j])
            RHO=(float(atmos['Total']))
            
            def arrasto(reb_sim):
                #latA,lonA,altA = transprojCart.transform(ps[1].x,ps[1].y,ps[1].z)
                #atmos = msise00.run(time=datetime(horaMeteoro.year,horaMeteoro.month,horaMeteoro.day,horaMeteoro.hour,horaMeteoro.minute,horaMeteoro.second), altkm=altA/1000., glat=latA, glon=lonA)
                #RHO=(float(atmos['Total']))
                ps[1].ax -= RHO*CD*ASection*(np.sqrt(ps[1].vx**2+ps[1].vy**2+ps[1].vz**2))*ps[1].vx/(2.*massaParticula)
                ps[1].ay -= RHO*CD*ASection*(np.sqrt(ps[1].vx**2+ps[1].vy**2+ps[1].vz**2))*ps[1].vy/(2.*massaParticula)
                ps[1].az -= RHO*CD*ASection*(np.sqrt(ps[1].vx**2+ps[1].vy**2+ps[1].vz**2))*ps[1].vz/(2.*massaParticula)

            sim.additional_forces = arrasto
            sim.force_is_velocity_dependent = 1
            sim.integrate(passo)
            
            tempo+=passo
            latA,lonA,altA = latM[j],lonM[j],altM[j]
            X[j],Y[j],Z[j],Vx[j],Vy[j],Vz[j] =ps[1].x,ps[1].y,ps[1].z,ps[1].vx,ps[1].vy,ps[1].vz
            latM[j],lonM[j],altM[j] = transprojCart.transform(ps[1].x,ps[1].y,ps[1].z)

            if(((altM[j]/1000)<1)):
                passo=0.00001/Vm
            if ((altM[j]/1000)<5):
                passo=0.2/Vm
            if ((altM[j]/1000)<10):
                passo=100/Vm
            

        print(massaPont[j],latA,lonA,altA)
        arquivo.write('  1-  '+str(tempo)+' g: '+str(lonA)+" , "+str(latA)+' , '+str(altA/1000.)+' @399 \n')
    arquivo.close()
    arquivoQueda.close()

    ###################################################################################################################
    #integracao pra tras
    # Integração reversa até 1000 km de altitude (dados salvos em arquivos .out e .dat)
    # Usada a massa em massaInt

    for i in range (len(massaPont)):
        X[i],Y[i],Z[i]=(X1[i]+X2[i])/2,(Y1[i]+Y2[i])/2,(Z1[i]+Z2[i])/2
        Vx[i],Vy[i],Vz[i]=Vx1[i],Vy1[i],Vz1[i]
        latM[i],lonM[i],altM[i] = transprojCart.transform(X[i],Y[i],Z[i])

    arquivoCart=open((variablesPIM.directorystr+'/Cartesian.dat'),'w')
    arquivoCoord=open((variablesPIM.directorystr+'/Coordinate.dat'),'w')

    arquivoCart.write("time(s) x y z vx vy vz \n")
    arquivoCoord.write("time(s) vel alt(km) lon lat \n")
    
    tempo=0
    passo=-5
    j=massaPont.index(massaInt)
    ASection=A[j]

    massaParticula=massaPont[j]

    while altM[j]<1000e3:
        os.system('clear')
        print(tempo,"altura atual (km): ",altM[j]/1000.)
        print(i, flush=True)
        
        Vm=np.sqrt(Vx[j]**2+Vy[j]**2+Vz[j]**2)
        
        if ((altM[j]/1000)>150) and ((altM[j]/1000)<990):
            passo=-10000/Vm
        else:
            passo=-2000/Vm
            
        strCart=str(str(tempo)+" "+str(X[j]/1000.)+" "+str(Y[j]/1000.)+" "+str(Z[j]/1000.)+" "+str(Vx[j]/1000.)+" "+
                    str(Vy[j]/1000.)+" "+str(Vz[j]/1000.)+" \n")
        arquivoCart.write(strCart)
        arquivoCoord.write(str(str(tempo)+" "+str(Vm)+" "+str(altM[j]/1000)+" "+str(lonM[j])+" "+str(latM[j])+" \n"))
        sim = rebound.Simulation()
        sim.integrator = "ias15"

        sim.units = ('m', 's', 'kg')
        sim.add(m=5.97219e24,hash='earth')
        meteor = rebound.Particle(m=massaPont[j],x=X[j],y=Y[j],z=Z[j],vx=Vx[j],vy=Vy[j],vz=Vz[j])
        sim.add(meteor)

        ps=sim.particles
        atmos = msise00.run(time=datetime(horaMeteoro.year,horaMeteoro.month,horaMeteoro.day,horaMeteoro.hour,horaMeteoro.minute,horaMeteoro.second), altkm=altM[j]/1000., glat=latM[j], glon=lonM[j])
        RHO=(float(atmos['Total']))
        def arrasto(reb_sim):
                    ps[1].ax -= RHO*CD*ASection*(np.sqrt(ps[1].vx**2+ps[1].vy**2+ps[1].vz**2))*ps[1].vx/(2.*massaParticula)
                    ps[1].ay -= RHO*CD*ASection*(np.sqrt(ps[1].vx**2+ps[1].vy**2+ps[1].vz**2))*ps[1].vy/(2.*massaParticula)
                    ps[1].az -= RHO*CD*ASection*(np.sqrt(ps[1].vx**2+ps[1].vy**2+ps[1].vz**2))*ps[1].vz/(2.*massaParticula)
        sim.additional_forces = arrasto
        sim.force_is_velocity_dependent = 1
        sim.integrate(passo)

        tempo+=passo
        X[j],Y[j],Z[j],Vx[j],Vy[j],Vz[j] =ps[1].x,ps[1].y,ps[1].z,ps[1].vx,ps[1].vy,ps[1].vz
        latM[j],lonM[j],altM[j] = transprojCart.transform(ps[1].x,ps[1].y,ps[1].z)

    with open((variablesPIM.directorystr+'/FinalCartesian.dat'),'w') as f:
        f.write(strCart)


    arquivoCart.close()
    arquivoCoord.close()
    ############################################################################################################
    # fazer arquivo com a trajetoria total do meteoro
    ##
    for line in reversed(list(open(variablesPIM.directorystr+'/coordinates.txt'))):
        print(line.rstrip())
        
    ################################################################################################################
    #salvar os dados dos pontos de queda do meteorito e vai gerar ao mapa de queda (primeira integraçao para frente)
    #   Análise dos pontos de queda e da integração reversa até 1000 km
    # (usa os arquivos .out salvo nos procedimentos anteriores)
    saida = pd.read_csv((variablesPIM.directorystr+'/saida.out'), sep='\s+',header=None)
    excluir = [0,2,4,6,7,8]
    saida.drop(saida.columns[excluir],axis=1,inplace=True)

    saida.insert(0, "mass", "Any")


    saida['mass'] = massaPont
    colunas = ['mass','time(s)','lon','lat']
    saida.columns = colunas

    arquivo=open((variablesPIM.directorystr+'/data.txt'),'a')
    arquivo.write(('\n \n Strewn Field: \n'))
    arquivo.write(saida.to_string(index=False))
    arquivo.write('\n \n')
    arquivo.close()

    # referente a integraçao pra tras (qunto tempo ele estava da entrada da atmosfera até chegar oa ponto do meteoro/ instante q ele entrou na atmosfera)
    with open(variablesPIM.directorystr+'/FinalCartesian.dat','r') as f:
        ent=f.read()
    fimTempoVoo=ent.index(" ")
    tempoVoo=float(ent[0:fimTempoVoo])
    tempoVooNum= timedelta(seconds=-tempoVoo)
    print("tempo de Voo para",massaInt," kg =",tempoVooNum)
    initialT=(horaMeteoro - tempoVooNum).strftime("%Y-%m-%d %H:%M:%S")
    #finalT=(horaMeteoro - tempoVooNum+timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    print("hora de entrada: ",initialT)

    #mapa de queda (integraçao para frente)

    saida['mass'] = saida['mass'].astype(str) + " kg"
    map_osm = folium.Map(
        location = [saida['lat'][saida.shape[0]//2], saida['lon'][saida.shape[0]//2]],
        zoom_start = 14
    )
    map_osm
    folium.Marker(
        location=[P1lat,P1lon],
        popup=folium.Popup('Initial Meteor',show=True),
        icon=folium.map.Icon(color='blue')
    ).add_to(map_osm)  
    folium.Marker(
        location=[P2lat,P2lon],
        popup=folium.Popup('Final Meteor',show=True),
        icon=folium.map.Icon(color='blue')
    ).add_to(map_osm)  

    for indice, row in saida.iterrows():
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=folium.Popup(row['mass'],show=True),
            icon=folium.map.Icon(color='yellow')
        ).add_to(map_osm)
    map_osm.save(variablesPIM.directorystr+'/strewnField.html')
    return

