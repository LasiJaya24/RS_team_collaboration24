#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sentinel-2 Water Surface Area Time Series
Job No: 241550
Created by Jason de Chastel (Senior Project Officer)
Date: 11/11/2025

This script processes satellite data to track water surface areas using Sentinel-2 data using Google Earth Engine.
"""

import ee
import pandas as pd
from datetime import datetime, timedelta, date
from google.cloud import storage
from google.oauth2 import service_account
from io import BytesIO
import time

# Initialize variables.
start_date = "2015-06-27"
end_date = date.today().strftime('%Y-%m-%d')
description = "sentinel2_daily_mndwi_statistics"
features = 'projects/remote-sensing-420704/assets/Waterbodies_qld_constructed'
output_filename = 'sentinel2_daily_mndwi_statistics.csv'
bucket = "sentinel2_timeseries"
service_account_json = r'\\bnefile34\groupdir\SWI\SPATIAL\Remote_Sensing\Projects\GEE\Service Key\remote-sensing-420704-a195c59596e7.json'

# Set Constants
CLD_PRB_THRESH = 50
MNDWI_THRESH = 0
SCALE = 10

# Function Definitions.
def get_s2_sr_cld_col(aoi, start_date, end_date):
    # Import and filter S2 SR.
    s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
        .filterBounds(aoi)
        .filterDate(start_date, end_date))
    # Import and filter s2cloudless.
    s2_cloudless_col = (ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
        .filterBounds(aoi)
        .filterDate(start_date, end_date))
    # Join the filtered s2cloudless collection to the SR collection by the 'system:index' property.
    return ee.ImageCollection(ee.Join.saveFirst('s2cloudless').apply(**{
        'primary': s2_sr_col,
        'secondary': s2_cloudless_col,
        'condition': ee.Filter.equals(**{
            'leftField': 'system:index',
            'rightField': 'system:index'
        })
    }))

def add_cloud_bands(img):
    # Get s2cloudless image, subset the probability band.
    cld_prb = ee.Image(img.get('s2cloudless')).select('probability')
    # Condition s2cloudless by the probability threshold value.
    is_cloud = cld_prb.gt(CLD_PRB_THRESH).rename('clouds')
    # Add the cloud probability layer and cloud mask as image bands.
    return img.addBands(ee.Image([cld_prb, is_cloud]))

def resample_to_10m(image):
    b11_resampled = image.select('B11').resample('bicubic')
    return image.addBands(b11_resampled, overwrite=True)

def time_series(feature, start_date):
    # Get the feature geometry
    geeFeatureGeometry = ee.Geometry(feature.geometry())

    def calculate_stats(image):       
        ### 1. Image prep
        # Get the image acquisition date and time in UTC
        image_date_utc = ee.Date(image.get('system:time_start'))
        image_date_aest = image_date_utc.advance(10, 'hour')
        # Clip to the boundary
        image_clip = image.clip(geeFeatureGeometry)
        # Resample B11 to 10m
        image_resample = resample_to_10m(image_clip)        

        ### 2. Cloud Area
        # Select band
        cloudmask = image.select('clouds')
        # Calculate band areas
        cloud_area = cloudmask.multiply(ee.Image.pixelArea()).rename('Cloud_Area')        

        ### 3. Water area
        # Compute MNDWI using normalized difference
        mndwi = image_resample.normalizedDifference(['B3', 'B11']).rename('MNDWI')
        # Mask the MNDWI image to include only water pixels
        mndwi_mask = mndwi.updateMask(cloudmask.Not()).gte(MNDWI_THRESH).rename('MNDWI_Mask')
        # Create a water area image
        water_area = mndwi_mask.multiply(ee.Image.pixelArea()).rename('MNDWI_Area')        

        ### 4. Total area
        # Create total pixel area image
        total_area = ee.Image.pixelArea().rename('Total_Area')
            
        ### 5. Combined areas
        # Combine pixel area images into a single Image with multiple bands
        combinedAreas = ee.Image.cat([
            water_area,
            cloud_area,
            total_area
        ])

        ### 6. Create statistics
        # Reduce regions to calculate statistics as dictionary
        statistics = combinedAreas.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geeFeatureGeometry,
            scale=SCALE
        )
        # Prepare stats dictionary
        stats_dict = {
            'date': image_date_aest.format('dd-MM-YYYY'),
            'pfi': feature.get('pfi'),
            'ufi': feature.get('ufi'),
            'mndwi_area': statistics.get('MNDWI_Area'),
            'cloud_area': statistics.get('Cloud_Area'),
            'total_area': statistics.get('Total_Area')
        }
        return ee.Feature(None, stats_dict)

    # Create Sentinel-2 image collection
    imageCollection = get_s2_sr_cld_col(geeFeatureGeometry, start_date, end_date)
    imageCollection = imageCollection.map(add_cloud_bands)
    # Generate statistics
    stats_collection = imageCollection.map(calculate_stats)
    return stats_collection

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

def initialize_gee(service_account_json):
    credentials = service_account.Credentials.from_service_account_file(
        service_account_json, 
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    ee.Initialize(credentials)

def find_last_capture_date(storage_client, bucket_name, output_filename):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.get_blob(output_filename)
    if blob:
        old_df = pd.read_csv(BytesIO(blob.download_as_string()), parse_dates=['date'])
        return old_df['date'].max().strftime('%Y-%m-%d')
    return None

def main(service_account_json, bucket_name, features, output_filename, description):
    # Initialize Google Earth Engine
    try:
        initialize_gee(service_account_json)
    except ee.EEException as e:
        print(f"Failed to initialize Google Earth Engine with error: {e}")
        return
    except FileNotFoundError:
        print(f"Service account file not found: {service_account_json}")
        return

    # Initialize Storage Client
    try:
        storage_client = storage.Client.from_service_account_json(service_account_json)
    except FileNotFoundError:
        print(f"Invalid service account JSON file path: {service_account_json}")
        return
    except service_account.exceptions.GoogleAuthError as e:
        print(f"Authentication failed with error: {e}")
        return

    # Find the last capture date
    try:
        last_capture_date = find_last_capture_date(storage_client, bucket_name, output_filename)
    except storage.exceptions.NotFound as e:
        print(f"Bucket or file not found with error: {e}")
        return
    except pd.errors.EmptyDataError as e:
        print(f"No data found in the CSV with error: {e}")
        return

    updated_start_date = start_date
    if last_capture_date:
        try:
            updated_start_date = (datetime.strptime(last_capture_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            print("Timeseries updating from date: {}".format(updated_start_date))
            description += f"_update_{datetime.now().strftime('%Y%m%d')}"
        except ValueError as e:
            print(f"Date parsing failed with error: {e}")
            return
    else:
        print("Creating new timeseries from date: {}".format(updated_start_date))

    # Create a feature collection for the waterbodies and map the time series analysis over it
    try:
        fc_server = ee.FeatureCollection(features)#.filter(ee.Filter.eq('pfi', '114006000066958'))
    except ee.EEException as e:
        print(f"Failed to create feature collection with error: {e}")
        return

    stats_series = None
    try:
        stats_series = fc_server.map(lambda feature: time_series(feature, updated_start_date))
    except ee.EEException as e:
        print(f"Failed during the mapping of time_series function with error: {e}")
        return

    # Flatten the results and export
    try:
        flattened_stats = ee.FeatureCollection(stats_series.flatten())
        export_daily_stats(flattened_stats, description, bucket_name)
    except ee.EEException as e:
        print(f"Failed to export statistics with error: {e}")
        return

if __name__ == '__main__':
    main(service_account_json, bucket, features, output_filename, description)
