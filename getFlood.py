"""
Created on Sat Apr  7 20:27:31 2018

@author: cranejohnson
"""

# required conda packages
# conda install -c menpo opencv
# conda install pyshp
# conda install -c conda-forge owslib
# conda update -n base conda
# conda install PIL
# conda install -c conda-forge simplekml

import cv2
from matplotlib import pyplot as plt
from datetime import datetime
import shapefile #reads shapefiles
import os,glob,sys
from PIL import Image
from shutil import copyfile
import imageio
import json
from collections import OrderedDict
import csv
import smtplib
import mimetypes
import email
import email.mime.application
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import zipfile
from os.path import basename
import simplekml

plt.switch_backend('agg')
plt.style.use('ggplot')


#print wms.identification.type
#print wms.identification.title
#print(wms['latest'].boundingBox)
#print(wms.getOperationByName('GetMap').formatOptions)

#  11 - MS - Missing
#  29 - WA - Water
#  80 - SI - Supra Water
# 100 - CS - Shadow
# 167 - LD - Land
# 179 - IC - Ice
# 200 - CL - Cloud
# 255 - SN - Snow
# 176 - 10
# 150 - 20
# 209 - 30
# 243 - 40
# 226 - 50
# 194 - 60
# 170 - 70
# 135 - 80
#  76 - 100



buffer = 0.2

height =1000
width = 1000

emailAddresses = ['benjamin.johnson@noaa.gov']

gdalPath = "/usr/bin/"
#gdalPath = "/Library/Frameworks/GDAL.framework/Versions/2.2/Programs/"

dirPath = os.path.dirname(os.path.realpath(__file__))

try:
    project_name = sys.argv[1]
except:
    project_name = 'Sag'

project = dirPath+"/projects/"+project_name+"/"

if not os.path.exists(project+"working"):
    os.makedirs(project+"working")
if not os.path.exists(project+"raw"):
    os.makedirs(project+"raw")
if not os.path.exists(project+"cloudFree"):
    os.makedirs(project+"cloudFree")
if not os.path.exists(project+"clipped"):
    os.makedirs(project+"clipped")

seriesData = OrderedDict()
cloudThreshold = 0.50



shapeFile= ''

for file in glob.glob(project+"clipShp/*.shp"):
    shapeFile = file


sf = shapefile.Reader(shapeFile)


llat = sf.bbox[1] - buffer*(sf.bbox[3]-sf.bbox[1])
ulat = sf.bbox[3] + buffer*(sf.bbox[3]-sf.bbox[1])
llon = sf.bbox[0] + buffer*(sf.bbox[0]-sf.bbox[2])
ulon = sf.bbox[2] - buffer*(sf.bbox[0]-sf.bbox[2])

xpix = (ulon - llon)/1000
ypix = -(ulat - llat)/1000

tfw = str(xpix)+"\n0\n0\n"+str(ypix)+"\n"+str(llon)+"\n"+str(ulat)

sys.stdout.flush()


if os.path.isfile(project+"jsonData.txt"):
    seriesData = json.load(open(project+"jsonData.txt"))



from owslib.wms import WebMapService
#wms = WebMapService('http://realearth.ssec.wisc.edu/cgi-bin/mapserv?map=RIVER-FLDall-AP.map', version='1.3.0')
wms = WebMapService('https://realearth.ssec.wisc.edu/cgi-bin/mapserv?map=RIVER-FLDall-AP.map&request=GetCapabilities&service=WMS&version=1.3')

firstRaw = 1
firstCloudFree = 1
newFiles = False
for layer in wms.contents:
    sys.stdout.flush()
    if "RIVER-FLDall-AP_" in layer:
        nextFile = False
        #Delete working files
        files = glob.glob(project+"working/*")
        for f in files:
            os.remove(f)

        print "Working on: ",layer

        parts = layer.split('_')

        datetime_object = datetime.strptime(parts[1]+parts[2], '%Y%m%d%H%M%S')

        #Check if we have already analyzed this image
        if str(datetime_object.strftime('%s')) in seriesData:
            print "Skipping: ",layer
            continue

        try:
            img = wms.getmap(layers=[layer],
                             srs='EPSG:4326',
                             bbox=(llon, llat, ulon, ulat),
                             size=(width,height),
                             format='image/tif',
                             transparent=False
                             )
        except:
            print "WMS failed"
            continue

        print "New Data for: ",layer
        out = open(project+"working/temp.tif", 'wb')
        out.write(img.read())
        out.close()


        text_file = open(project+"working/temp.tfw", "w")
        text_file.write(tfw)
        text_file.close()

        #Need to use PIL Image.open to check for corrupt file
        try:
            im=Image.open(project+"working/temp.tif")
            imgOrig = cv2.imread(project+"working/temp.tif")
        except:
            print "Corrupt Image"
            continue


        img = cv2.cvtColor(imgOrig, cv2.COLOR_BGR2GRAY)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(imgOrig,datetime_object.strftime('%m/%d/%Y %H:%M UTC'),(0,height-10), font, 1,(0,0,0),3,2)
        cv2.imwrite(project+"working/temp.tif", imgOrig)
        # create the histogram
        histogram = cv2.calcHist([img], [0], None, [256], [0, 256])

        # configure and draw the histogram figure
        #plt.figure()
        #plt.title("Grayscale Histogram")
        #plt.xlabel("grayscale value")
        #plt.ylabel("pixels")
        #plt.xlim([0, 256])

        i = 0
        cloudy = histogram[200]/(height*width)
        cloudyStr =  "{0:.2f}".format(cloudy[0])


        #Check if the image has 'noData'
        if histogram[255] == height*width:
            seriesData[int(datetime_object.strftime('%s'))] = {}
            continue

        #If we make it this far the image has data in it........
        #Save a geotiff in the raw output folder
        newFiles = True

        os.system(gdalPath+"gdal_translate -co \"COMPRESS=LZW\" -a_srs EPSG:4326 "+project+"working/temp.tif "+project+"raw/"+layer+"_"+cloudyStr+".tif")
        if firstRaw:
            copyfile(project+"raw/"+layer+"_"+cloudyStr+".tif",project+project_name+"_latest_raw.tif" )
            firstRaw = 0
        print "Cloudy: ",cloudy

        #If the image is too cloudy just save the file to the raw directory
        if cloudy > cloudThreshold:
            cloudyStr =  "{0:.2f}".format(cloudy[0])
            cv2.imwrite( project+"working/cloudy.tif", imgOrig );
            text_file = open(project+"working/cloudy.tfw", "w")
            text_file.write(tfw)
            text_file.close()
            seriesData[int(datetime_object.strftime('%s'))] = {}
            continue

        #Clip the image based on the shape file
        os.system(gdalPath+"gdalwarp -co \"COMPRESS=LZW\" -cutline "+shapeFile+" -crop_to_cutline  -dstalpha "+project+"raw/"+layer+"_"+cloudyStr+".tif"+" "+project+"working/clipped.tif")

        #Need to use PIL Image.open to check for corrupt file
        try:
            im=Image.open(project+'working/clipped.tif')
            copyfile(project+'working/clipped.tif',project+"clipped/"+layer+"_"+cloudyStr+".tif")
            if firstCloudFree:
                copyfile(project+"clipped/"+layer+"_"+cloudyStr+".tif",project+project_name+"_latest_clipped.tif")
            clippedImg = cv2.imread(project+'working/clipped.tif')
            clippedImg = cv2.cvtColor(clippedImg, cv2.COLOR_BGR2GRAY)
            # create the histogram
            histogram = cv2.calcHist([clippedImg], [0], None, [256], [0, 256])
        except:
            print "Corrupt Image"
            continue
        #Process the clipped image so that we only count flood pixels in the AOI
#  11 - MS - Missing
#  29 - WA - Water
#  80 - SI - Supra Water
# 100 - CS - Shadow
# 167 - LD - Land
# 179 - IC - Ice
# 200 - CL - Cloud
# 255 - SN - Snow
# 176 - 10
# 150 - 20
# 209 - 30
# 243 - 40
# 226 - 50
# 194 - 60
# 170 - 70
# 135 - 80
#  76 - 100
        MS = 0
        WA = 0
        SI = 0
        CS = 0
        LD = 0
        IC = 0
        CL = 0
        SN = 0
        FL = 0

        for pix in histogram:
            if i == 80:
                SI = pix[0]
                os.system(gdalPath+"gdal_translate -a_srs EPSG:4326 -co \"COMPRESS=LZW\" "+project+"working/temp.tif "+project+"cloudFree/"+layer+"_"+cloudyStr+".tif")
                if firstCloudFree:
                    copyfile(project+"cloudFree/"+layer+"_"+cloudyStr+".tif",project+project_name+"_latest_cloudFree.tif" )
                    firstCloudFree = 0
            if i == 255:
                SN = pix[0]
            if i == 11:
                MS = pix[0]
            if i == 29:
                WA = pix[0]
            if i == 100:
                CS = pix[0]
            if i == 167:
                LD = pix[0]
            if i == 179:
                IC = pix[0]
            if i == 200:
                CL = pix[0]
            if i == 150:
                FL = FL + pix[0]*0.2
            if i == 209:
                FL = FL + pix[0]*0.3
            if i == 243:
                FL = FL + pix[0]*0.4
            if i == 226:
                FL = FL + pix[0]*0.5
            if i == 194:
                FL = FL + pix[0]*0.6
            if i == 170:
                FL = FL + pix[0]*0.7
            if i == 135:
                FL = FL + pix[0]*0.8
            if i == 76:
                FL = FL + pix[0]
            i=i+1
        seriesData[int(datetime_object.strftime('%s'))] = {'SN':int(SN),'FL':int(FL),'CL':int(CL),'SI':int(SI),'MS':int(MS),'WA':int(WA),'CS':int(CS),'LD':int(LD),'IC':int(IC)}
        sys.stdout.flush()



#OrderedDict(sorted(seriesData['SI'].items()))
with open(project+'jsonData.txt', 'w') as outfile:
    json.dump(seriesData, outfile,indent=4)

try:
    with open(project+'emailList.csv', 'r') as f:
        reader = csv.reader(f)
        emailAddresses = list(reader)[0]
except:
    print "No email List"

#newFiles = True
if newFiles:

    images = []
    files = sorted(glob.glob(project+'cloudFree/*'))

    i = len(files)-10
    while i < len(files):
        images.append(imageio.imread(files[i]))
        i += 1
    imageio.mimsave(project+project_name+'_animated_last10.gif', images,fps=1)


    #SEND AN EMAIL WITH THE NEW IMAGE
    msg = MIMEMultipart()
    msg['Subject'] = "New Flood Product for "+project_name
    msg['From'] = 'hydro@redrock'
    msg['To'] = ', '.join(emailAddresses)


    text = MIMEText("http://140.90.218.62/tools/getFlood/projects/"+project_name+"\n\n\nLatest Raw image, cloud free image and last 10 cloud free images animated are attached. The latest image has clound cover: "+str(cloudy)+"%")
    msg.attach(text)

    if os.path.isfile(project+project_name+"_latest_raw.tif"):
        ImgFileName = project+project_name+"_latest_raw.tif"
        img_data = open(ImgFileName, 'rb').read()
        image = MIMEImage(img_data, name=os.path.basename(ImgFileName))
        msg.attach(image)

    if os.path.isfile(project+project_name+"_latest_cloudFree.tif"):
        ImgFileName = project+project_name+"_latest_cloudFree.tif"
        img_data = open(ImgFileName, 'rb').read()
        image = MIMEImage(img_data, name=os.path.basename(ImgFileName))
        msg.attach(image)

    if os.path.isfile(project+project_name+"_animated_last10.gif"):
        ImgFileName = project+project_name+"_animated_last10.gif"
        img_data = open(ImgFileName, 'rb').read()
        image = MIMEImage(img_data, name=os.path.basename(ImgFileName))
        msg.attach(image)

    d= {
         'project': project_name,
         'llat' : llat,
         'ulat' : ulat,
         'llon' : llon,
         'ulon' : ulon,
         'cllat' : sf.bbox[1],
         'culat' : sf.bbox[3],
         'cllon' : sf.bbox[0],
         'culon' : sf.bbox[2],

         }


    print 'creating archive'
    zipFileName = project+'latestData.kmz'
    zf = zipfile.ZipFile(zipFileName, mode='w')
    try:
        zf.write(project+project_name+"_latest_cloudFree.tif",basename(project+project_name+"_latest_cloudFree.tif"))
        zf.write(project+project_name+"_latest_raw.tif",basename(project+project_name+"_latest_raw.tif"))
        zf.write(project+project_name+"_latest_clipped.tif",basename(project+project_name+"_latest_clipped.tif"))
    finally:
        print 'closing'



    kml = simplekml.Kml()
    box = simplekml.LatLonBox()
    box.north = ulat
    box.south = llat
    box.east = ulon
    box.west = llon
    clipBox = simplekml.LatLonBox()
    clipBox.north = sf.bbox[3]
    clipBox.south = sf.bbox[1]
    clipBox.east = sf.bbox[2]
    clipBox.west = sf.bbox[0]

    fol = kml.newfolder(name='Latest Images')
    cloudFree = fol.newgroundoverlay(name= "Latest Cloud Free")
    cloudFree.icon.href = project_name+"_latest_cloudFree.tif"
    cloudFree.latlonbox = box
    raw = fol.newgroundoverlay(name="Latest Raw");
    raw.icon.href = project_name+"_latest_raw.tif"
    raw.latlonbox = box
    raw.visibility = 0
    clip = fol.newgroundoverlay(name="Latest Clipped");
    clip.icon.href = project_name+"_latest_clipped.tif"
    clip.latlonbox = clipBox
    clip.visibility = 0
    cloudFreeSeries = kml.newfolder(name='Cloud Free Time Series')

    files = sorted(glob.glob(project+'cloudFree/*'))
    for f in files:
        cloudFree = cloudFreeSeries.newgroundoverlay(name= os.path.basename(f))
        cloudFree.icon.href = os.path.basename(f)
        cloudFree.latlonbox = box
        parts = os.path.basename(f).split("_")
        datetime_object = datetime.strptime(parts[1]+parts[2], '%Y%m%d%H%M%S')
        cloudFree.timespan.begin = datetime_object.strftime('%Y-%m-%dT%H:00:00')
        cloudFree.visibility = 0
        try:
            zf.write(f,os.path.basename(f))
        finally:
            print 'finished'

    kml.save(project+"/Latest_image.kml")
    zf.write(project+"Latest_image.kml",basename(project+"Latest_image.kml"))
    zf.close()
    os.remove(project+"/Latest_image.kml")


    # KML attachment
    ImgFileName = 'latestData_'+datetime_object.strftime('%Y-%m-%dT%H:00')+'.kmz'
    fp=open(zipFileName,'rb')
    att = email.mime.application.MIMEApplication(fp.read(),_subtype="kmz")
    att.add_header('Content-Disposition','attachment',filename=ImgFileName)
    msg.attach(att)


    try:
        s = smtplib.SMTP('localhost')
        s.sendmail('hydro@redrock',emailAddresses, msg.as_string())
        s.quit()
    except:
        print "No email List"



    images = []
    files = sorted(glob.glob(project+'cloudFree/*'))
    for f in files:
        images.append(imageio.imread(f))
    imageio.mimsave(project+project_name+'_animated.gif', images,fps=2,loop=1)




    colors = ['Purple','black','Red','DarkBlue','Green','yellow']
    i=0
    for pixelType in ['SI','FL','IC','WA','SN']:
        tsVal = []
        tsTime = []
        for key in seriesData:
            try:
                if pixelType in seriesData[key]:
                    tsVal.append(seriesData[key][pixelType])
                    tsTime.append(datetime.fromtimestamp(int(key)))
            except ValueError:
                pass  # it was a string, not an int.

        plt.figure(i+2,figsize=(10,4),dpi=100)
        print(pixelType)
        print(tsTime)
        print(tsVal)
        plt.plot_date(x=tsTime,y=tsVal,markerfacecolor=colors[i], markeredgecolor='white',label=pixelType)
        plt.ylabel('Number of Pixels')
        plt.legend(loc='upper left', shadow=True)
        plt.xticks(rotation=90)
        plt.savefig(project+pixelType+"_"+project_name+".jpg",bbox_inches='tight',figsize=(8,4),dpi=200)
        plt.figure(1,figsize=(10,4),dpi=100)
        plt.plot_date(x=tsTime,y=tsVal,markerfacecolor=colors[i], markeredgecolor='white',label=pixelType)
        plt.ylabel('Number of Pixels')
        plt.legend(loc='upper left', shadow=True,ncol=6)
        plt.xticks(rotation=90)
        plt.savefig(project+"All_"+project_name+".jpg",bbox_inches='tight',figsize=(8,4),dpi=200)
        i = i + 1

print "Done"
