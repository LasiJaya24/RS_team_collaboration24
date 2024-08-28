# Landsat MNDWI Timeseries
# Created by Jason de Chastel
# Remote Sensing Team
# 26/08/2024

### 1. Import modules
print("Starting Landsat MNDWI Timeseries Update")
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

### 3. Declare variables
print("3. Declaring variables")

features = 'projects/remote-sensing-420704/assets/Waterbodies_qld_constructed'
BUCKET = 'landsat_timeseries'
uniqueid_field = 'pfi'
mdwiThresh = 0.1
albers_projection = ee.Projection('EPSG:3577')
output_filename = 'landsat_daily_mndwi_statistics.csv'

### 4. Define functions
print("4. Defining functions")

# Create a function to apply the correct cloud mask based on the available bands.
def apply_cloud_mask(image):
    # Select the 'pixel QA' band from the current image.
    qa = image.select('QA_PIXEL')
    # Determine cloud mask bits based on satellite data.
    cloud_mask = ee.Image(ee.Algorithms.If(
        image.bandNames().contains("SR_B6"),
        qa.bitwiseAnd(1 << 7).Or(qa.bitwiseAnd(1 << 3)),  # Adjusted for L7
        qa.bitwiseAnd(1 << 5).Or(qa.bitwiseAnd(1 << 3))   # Adjusted for L5, L8, L9
    ))
    return cloud_mask

def time_series(feature):
    geeFeatureGeometry = ee.Geometry(feature.geometry())
    dateRange = ee.DateRange(start_date, end_date)

    def calculate_stats(image):
        # Apply the cloud mask
        cloud_mask = apply_cloud_mask(image)
        # Calculate the area of cloud coverage within the image
        cloud_area = cloud_mask.multiply(ee.Image.pixelArea()).reproject(crs=albers_projection, scale=30).rename('Cloud_Area')   
        # Determine bands based on satellite platform
        band_names = image.bandNames()
        # Earth Engine's server-side objects use different methods
        green_band = ee.Algorithms.If(band_names.contains('SR_B6'), 'SR_B3', 'SR_B2')
        swir_band = ee.Algorithms.If(band_names.contains('SR_B6'), 'SR_B6', 'SR_B5')
        # Since ee.Algorithms.If() returns an ee.ComputedObject, you'll need to cast the result to a string
        green_band = ee.String(green_band)
        swir_band = ee.String(swir_band)    
        # Calculate MNDWI
        mndwi = image.normalizedDifference([green_band, swir_band]).rename('MNDWI')
        # Mask the MNDWI image to include only water pixels
        mndwi_mask = mndwi.gte(mdwiThresh).rename('MNDWI_Mask')        
        # Create a water pixel area image
        water_pixel_area = mndwi_mask.multiply(ee.Image.pixelArea()).reproject(crs=albers_projection, scale=30).rename('MNDWI_Area')     
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
            scale=30,
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
    # Load Landsat 5 & 7 & 8
    l5 = ee.ImageCollection("LANDSAT/LT05/C02/T2_L2")
    l7 = ee.ImageCollection("LANDSAT/LE07/C02/T2_L2")
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T2_L2")
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T2_L2")
    # Merge Landsat 5 & 7
    landsat_combined = l5.merge(l7).merge(l8).merge(l9)
    # Filter merged collection by feature's geometry and date range, and calculate stats
    filtered_images = landsat_combined.filterBounds(geeFeatureGeometry).filterDate(dateRange).map(calculate_stats)

    return filtered_images    
    
def export_daily_stats(stats_feature_collection, description, bucket_name):
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
        description = f'landsat_update_{datetime.now().strftime("%Y%m%d")}'
        print("   " + start_date)
    else:
        print("    Master CSV file not found. Creating new file.")
        # Analysis period
        start_date = "1900-01-01"
        end_date = "2024-08-01"
        description = "landsat_daily_mndwi_statistics"

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
