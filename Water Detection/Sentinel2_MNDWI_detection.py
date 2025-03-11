#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sentinel-2 MNDWI Detection
Job No: 251851
Created by Jason de Chastel (Senior Project Officer)
Date: 11/03/2025

This script processes satellite data to detect water areas using Sentinel-2 imagery and MNDWI.
"""

# Import modules
import ee
from google.oauth2 import service_account
from google.cloud import storage
import time

# Initialize variables
description = "Sentinel2-Detection-Mainland"
features = 'projects/remote-sensing-420704/assets/Mainland'
bucket = "sentinel2_detection"
service_account_json = r'\\bnefile34\groupdir\SWI\SPATIAL\Remote_Sensing\Projects\GEE\Service Key\remote-sensing-420704-a195c59596e7.json'

# Set up parameters
start_date = '2024-01-01'
end_date = '2025-01-01'
mndwi_threshold = 0.0
cloud_prob_threshold = 50
min_area_threshold = 10000

# Define functions
def initialize_gee(service_account_json):
    credentials = service_account.Credentials.from_service_account_file(
        service_account_json, 
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    ee.Initialize(credentials)
    
# Function to apply cloud masking, resample the SWIR band and calculate MNDWI
def apply_processing(image):
    # Get the corresponding cloud probability image
    cloudProbImage = ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY') \
        .filter(ee.Filter.eq('system:index', image.get('system:index'))) \
        .first() \
        .select('probability')
    # Create the cloud mask
    cloudMask = cloudProbImage.lte(cloud_prob_threshold)
    # Apply the cloud mask
    imageCloudMasked = image.updateMask(cloudMask)
    # Resample the SWIR band (Band 11) to 10 meters using bicubic interpolation
    swir_resampled = imageCloudMasked.select('B11').resample('bicubic')
    # Calculate MNDWI using the resampled band
    mndwi = imageCloudMasked.normalizedDifference(['B3', swir_resampled.select('B11').bandNames().get(0)]).rename('MNDWI')
    # Add the MNDWI band to the cloud-masked image
    return imageCloudMasked.addBands(mndwi)

# Function to compute the feature's geometry area in square meters and add it as a property
def add_area(feature):
    patch_area = ee.Number(feature.geometry().area(1))
    return feature.set({'area_m2': patch_area})

# Function to add start_date and end_date as properties to each feature
def add_dates(feature):
    return feature.set({'start_date': start_date, 'end_date': end_date})

# Function to add centroid coordinates to each feature
def add_centroid_coords(feature):
    centroid = feature.geometry().centroid(1)
    coords = ee.List(centroid.coordinates())
    return feature.set({
        'centroid_x': ee.Number(coords.get(0)),
        'centroid_y': ee.Number(coords.get(1))
    })

def main(service_account_json, bucket_name, features, description):
    # Initialize Google Earth Engine
    try:
        print("1. Initialising GEE")
        initialize_gee(service_account_json)
    except ee.EEException as e:
        print(f"Failed to initialize Google Earth Engine with error: {e}")
        return
    except FileNotFoundError:
        print(f"Service account file not found: {service_account_json}")
        return

    # Initialize Storage Client
    try:
        print("2. Initialising Storage")
        storage_client = storage.Client.from_service_account_json(service_account_json)
    except FileNotFoundError:
        print(f"Invalid service account JSON file path: {service_account_json}")
        return
    except service_account.exceptions.GoogleAuthError as e:
        print(f"Authentication failed with error: {e}")

    # Create a feature collection for the catchment
    try:
        print("3. Processing Imagery")

        # Load the water plan feature
        fc_server = ee.FeatureCollection(features)

        # Load and clip the Sentinel-2 harmonized data collection to the ROI
        s2HarmonizedCollection = (ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
                                    .filterDate(start_date, end_date)
                                    .filterBounds(fc_server)
                                    .map(lambda image: image.clip(fc_server)))

        # Map the function over the image collection
        mndwiCollection = s2HarmonizedCollection.map(apply_processing)

        # Find average MNDWI
        averageMNDWI = mndwiCollection.select('MNDWI').mean()

        # Apply the MNDWI threshold to create a binary water mask
        mask = averageMNDWI.gt(mndwi_threshold).selfMask()

        # Convert binary water mask to vector polygons
        waterPolygonsAverage = mask.reduceToVectors(
            geometry=fc_server,
            scale=10,
            geometryType='polygon',
            eightConnected=False,
            bestEffort=True,
            labelProperty='water',
        )

        # Apply the date info to each feature
        waterPolygonsAverage = waterPolygonsAverage.map(add_dates)

        # Add the area field
        waterPolygonsAverage = waterPolygonsAverage.map(add_area)

        # Add centroid coordinates to each feature
        waterPolygonsAverage = waterPolygonsAverage.map(add_centroid_coords)

        # Filter by area
        waterPolygonsAverage = waterPolygonsAverage.filter(ee.Filter.gt('area_m2', min_area_threshold))

        # Include start_date and end_date in the file name prefix to reflect in the exported Shapefile
        fileNamePrefix = f"{description}_{start_date}_{end_date}"
            
        # Export the daily statistics to Google Cloud Storage
        export_task = ee.batch.Export.table.toCloudStorage(
            collection=ee.FeatureCollection(waterPolygonsAverage),
            description=fileNamePrefix,
            bucket=bucket,
            fileNamePrefix=fileNamePrefix,
            fileFormat='SHP'
        )
        export_task.start()

    except ee.EEException as e:
        print(f"Failed to create feature collection with error: {e}")
        return

    print("4. Finished Processing. Check Task Manager for job status.")

# Run the main script
if __name__ == '__main__':
    print("Sentinel-2 MNDWI Detection")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")
    main(service_account_json, bucket, features, description)
