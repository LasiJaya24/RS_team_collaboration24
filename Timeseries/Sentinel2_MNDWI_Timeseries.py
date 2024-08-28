# Sentinel2 MNDWI Timeseries Update
# Created by Jason de Chastel
# Remote Sensing Team
# 26/08/2024

### 1. Import modules
print("Starting Sentinel2 MNDWI Timeseries Update")
print("1. Import modules")

import ee
import pandas as pd
from datetime import datetime, timedelta, date
from google.cloud import storage
from google.oauth2 import service_account
from io import BytesIO
import time
import sys

### 2. Initialize GEE with the service account credentials
print("2. Initialising GEE")

try:
    SERVICE_ACCOUNT_JSON = r'K:\Projects\GEE\Service Key\remote-sensing-420704-a195c59596e7.json'
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_JSON, 
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    ee.Initialize(credentials)
except:
    print("Initialisation failed")
    sys.exit()

### 3. Declare Variables
print("3. Declaring variables")

features = 'projects/remote-sensing-420704/assets/Waterbodies_qld_constructed'
output_filename = 'sentinel2_daily_mndwi_statistics.csv'
uniqueid_field = "pfi"
mdwiThresh = 0.1
BUCKET = "sentinel2_timeseries"
albers_projection = ee.Projection('EPSG:3577')

### 4. Define Functions
print("4. Defining functions")

def time_series(feature):
    geeFeatureGeometry = ee.Geometry(feature.geometry())
    dateRange = ee.DateRange(start_date, end_date)

    def resample_to_10m(image):
        # Resample the SWIR band (B11) to 10m using bicubic interpolation
        b11_resampled = image.select('B11').resample('bicubic').reproject(crs=albers_projection, scale=10)
        # Create a new image with the resampled B11 band and original 10m bands
        return image.addBands(b11_resampled, overwrite=True)

    def calculate_stats(image):       
        # Compute MNDWI using the resampled bands
        mndwi = image.normalizedDifference(['B3', 'B11']).rename('MNDWI')                
        # Mask the MNDWI image to include only water pixels
        mndwi_mask = mndwi.gte(mdwiThresh).rename('MNDWI_Mask')        
        # Create a water pixel area image
        water_pixel_area = mndwi_mask.multiply(ee.Image.pixelArea()).reproject(crs=albers_projection, scale=10).rename('MNDWI_Area')        
        # Calculate cloud pixels and area
        cloud_mask = image.select('QA60').bitwiseAnd(1 << 10).Or(image.select('QA60').bitwiseAnd(1 << 11)).eq(1)
        cloud_area = cloud_mask.multiply(ee.Image.pixelArea()).rename('Cloud_Area')        
        # Create total pixel area image
        total_pixel_area = ee.Image.pixelArea().rename('Total_Area')
        # Combine pixel area images into a single Image with multiple bands
        combinedAreas = ee.Image.cat([
            water_pixel_area,
            cloud_area,
            total_pixel_area
        ])
        # Reduce regions to calculate statistics as dictionary
        statistics = combinedAreas.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geeFeatureGeometry,
            scale=10,
            crs=albers_projection
        )
        # Calculate the percentage of water and cloud cover
        water_percent = ee.Number(statistics.get('MNDWI_Area')).divide(statistics.get('Total_Area')).multiply(100)
        cloud_percent = ee.Number(statistics.get('Cloud_Area')).divide(statistics.get('Total_Area')).multiply(100)
        # Compile a dictionary of statistics
        stats_dict = {
            'date': image.date().format('YYYY-MM-dd'),
            uniqueid_field: feature.get(uniqueid_field),
            'mndwi_area': statistics.get('MNDWI_Area'),
            'cloud_area': statistics.get('Cloud_Area'),
            'total_area': statistics.get('Total_Area'),
            'mndwi_percent': water_percent,
            'cloud_percent': cloud_percent
        }
        return ee.Feature(None, stats_dict)    
    
    # Create an ImageCollection for the feature and map the calculate_stats function
    return ee.ImageCollection('COPERNICUS/S2_HARMONIZED') \
        .filterBounds(geeFeatureGeometry)\
        .filterDate(dateRange)\
        .map(resample_to_10m)\
        .map(calculate_stats)

def export_daily_stats(stats_feature_collection, description, bucket_name):
    # Export the daily statistics to Google Cloud Storage and monitor the task status
    export_task = ee.batch.Export.table.toCloudStorage(
        collection=ee.FeatureCollection(stats_feature_collection),
        description=description,
        bucket=bucket_name,
        fileNamePrefix=description,
        fileFormat='CSV'
    )
    export_task.start()
    print("Finished - Check Google Earth Engine for task status")

### 5. Find last capture date
print("5. Finding last capture date")

try:

    # Initialize storage client
    storage_client = storage.Client.from_service_account_json(SERVICE_ACCOUNT_JSON)
    bucket = storage_client.get_bucket(BUCKET)
    blob = bucket.get_blob(output_filename)

    # Check if master CSV exists and extract last capture date
    if blob is not None:
        # Download the contents of the blob as a string and convert it to a DataFrame        
        old_df = pd.read_csv(BytesIO(blob.download_as_string()), parse_dates=['date'])
        start_date = (old_df['date'].max() + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = date.today().strftime('%Y-%m-%d')
        description = f'sentinel2_update_{datetime.now().strftime("%Y%m%d")}'
        print("    " + start_date)    
    else:
        print("     Master CSV file not found. Creating new file.")
        # Analysis period
        start_date = "1900-01-01"
        end_date = "2030-01-01"
        description = "sentinel2_daily_mndwi_statistics"

except:
    print("Error: Storage bucket not found")
    sys.exit()

### 6. Run timeseries of waterbodies
print("6. Create waterbody feature collection")

try:
    # Generate and export statistics
    fc_server = ee.FeatureCollection(features)
except:
    print("Error: Waterbody features not found")
    sys.exit()

### 7. For each waterbody, calculate daily statistics
print("7. Calculating daily statistics")

try:
    stats_collections = fc_server.map(time_series)
    flattened_stats = ee.FeatureCollection(stats_collections.flatten())
except:
    print("Error: Calculating statistics failed")
    sys.exit()

### 7. Export data to cloud bucket
print("8. Exporting data to cloud bucket")

try:
    # Start the export process
    export_daily_stats(flattened_stats, description, BUCKET)
except:
    print("Error: Exporting statistics to cloud bucket failed")
    sys.exit()
