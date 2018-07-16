1.  Create a new project directory with a simple project name, no special characters
2.  Create a new folder called clipShp inside of the new project directory
3.  Add a shapefile to the clipShp directory with a single polygon with the area of interest
      - Good site to generate a shapefile: https://gis.ucla.edu/apps/click2shp/
      - Need to click the polygon option first
      - Minimum dbf,prj,shp,shx parts
4.  Add a file called "emailList.csv" with comma deliminated email addressess for cloud free image delivery
5.  Run the this command in redrock: python /var/www/html/tools/getFlood/getFlood.py <project_name>
6.  Set this command up on an hourly cron to check for new Satellite images
 