# Planet Labs Python Time Series

## Table of contents

- [Installation](#installation)

    Ensure the following Python modules are installed

    NumPy	    1.24.4
  
    pandas	    2.0.3
  
    GeoPandas	0.12.2
  
    PIL	        9.5.0
  
    pytz	    2024.1
  
    rasterio	1.3.7
  
    XlsxWriter	3.2.0
  
  
    Download:

    https://github.com/LasiJaya24/RS_team_collaboration24/blob/main/Timeseries/Planet_NDWI_Time_Series.ipynb
    
 - [Usage](#usage)

    On running the script you will be presented with a simple form to complete.
   ![image](https://github.com/user-attachments/assets/2991ed3c-1b74-4506-8066-9f5efcc0a77b)


    This form requires:

    Job ID – Remote Sensing Job ID  
    PFI – Persistent Feature Identifier  
    Name – The name of the person running the script  
    NDWI Threshold – Which can range from -1 to 1  
    Matplotlib colourmap – These are pre-defined colourmap selections, with the option to include custom colourmaps  
    Imagery – Path to the location of downloaded Planet Labs imagery  
    Shapefile – Path to AOI  
    Output – Path to user selected location of output folder  



#### Changelog

Version 0.1

Planet code initially written by Jason Dechastel using NWDI index to detect water using Planet Labs imagery

Version 0.2

Corrected NDWI formula in function, and then loop  
Removed NDWI function as it wasn’t being used in the loop  
Added NDVI to detect turbulent water for water storage analysis  
Added colour PNG for NDWI and NDVI


Version 0.3 - 04/10/2024

Removed unused Python modules  
Removed NDWI code  
Remove above and below threshold functions  
Added single function to do both  
Removed other unused functions  
Added function to generate friendly EPSG names when checking projections  
Added function to prepend AEST time to output image names  
Read input raster, and process raster in RAM and write output files  
Only write out NDVI GeoTIFF, and colour stretch PNG  
Automatically creates output folder if it doesn’t exist  


Version 0.4 - 11/10/2024

Added software version  
Improved code documentation  
Add Job Details section for manual metadata collection  
Automatically create output sub folder in notebook folder with execution date and time prepended  
Create Excel file output instead of CSV  
Excel output filename adds execution date and time, Job ID, and PFI  
Excel file contains NDVI Output, and Job Metadata tabs  
Allows changing of colour map by editing one variable  
Metadata tab contains manually and automatically collected metadata

Start Date and Time  
End Date and Time  
Total Time HH:MM:SS.ss  
Job ID  
PFI  
Analyst  
X Pixel Resolution (m)  
Y Pixel Resolution (m)  
Pixel Area (sqm)  
Software Version  
Colour Map Used  

Version 0.5 - 31/10/2024

Re-arrange manual input variables so at beginning of script  
Re-arrange meta data display order in output Excel  
Added Python modules used in script with version  

Changed to integer values as float not required  

x_res = int(transform.a)  # Resolution in x direction (transform[0])  
y_res = int(transform.e)  # Resolution in y direction (transform[4])  
pixel_area_m2 = int(x_res * (y_res))  

Changed output folder to local user profile Documents  
Changed filename and location of check projection plot. It now has same name format as Excel filename, and is now included in the output folder.  


Metadata tab now additionally includes:

Python Version  
Python Environment  
Shapefile EPSG code and projection name  
Raster EPSG code and projection name  


Version 0.6 18/11/2024

Added GUI using tkinter

Includes  
Queensland Coat of Arms  
SCII branding  
Fields for meta data collection  
Dropdown for Analyst and Colour Map  
Ability to browse for source and destination items  
Added corporate colours  
Collect even more metadata automatically  
Shows Remote Sensing Team email address as well as software version  


Version 0.7 – 28/01/2025 

Added filter for shapefile selection  
Add logic to cope with AnalyticMS_SR and AnalyticMS string replacement for syncing of udm2 files to true colour  
Area and percentage of cloud, haze, and shadow now added  
Showing plots of UDM mask with values for selected AOI  
Added index classified mask raster for values set above the user threshold and can have colour changed  
Added ha calculation for area  
Calculates negative values for NDVI water detection  
Writes AEST date and time onto colour output  
Converts UTC processing date to AEST date  

Version 9999

TBA
