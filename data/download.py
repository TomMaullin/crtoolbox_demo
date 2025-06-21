import os
import gzip
import shutil
import requests
import warnings
import pandas as pd
from nilearn.datasets import fetch_neurovault

def download_5802_contrasts(n=5, contrasts=None, data_dir=None):

    # Print warning if n too high
    if n > 179:
        print('Warning: Data only available for 179 subjects!')
        
    # Load in the collection
    collection_id = 5802
    url = f"https://neurovault.org/api/collections/{collection_id}/images/?format=json"
    
    # Get the collection metadata
    all_images = []
    while url:
        response = requests.get(url)
        data = response.json()
        all_images.extend(data['results'])
        url = data['next']  # Follow pagination
    
    # Convert to pandas dataframe
    meta_df = pd.DataFrame(all_images)
    
    # Drop subject with corrupted contrast
    meta_df = meta_df[meta_df['id'] != 135107].reset_index(drop=True)
    
    # Check if we have been given any contrasts
    if contrasts is None:
        contrasts = [
            'Faces NimStim Faces vs Shapes',
            'IAPS LookNeg vs LookNeut'
        ]

    # Extract subject ID and contrast name
    meta_df = meta_df.copy()
    meta_df['subject'] = meta_df['name'].str.extract(r'^Subject (\d{3})')[0]
    meta_df['contrast'] = meta_df['name'].str.extract(r'^Subject \d{3} (.+)$')[0]

    # Find subjects with both contrasts
    grouped = meta_df.groupby('subject')['contrast'].apply(set)
    eligible_subjects = grouped[grouped.apply(lambda s: set(contrasts).issubset(s))].index[:n]

    # Define image filter for nilearn
    def image_filter(im):
        name = im.get('name', '')
        return any(
            name.startswith(f"Subject {subj} {contrast}")
            for subj in eligible_subjects
            for contrast in contrasts
        )

    print(f"Downloading for subjects: {list(eligible_subjects)}")

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="You specified a value for `image_filter` but the default filters in `image_terms` still apply.",
            category=UserWarning
        )
        nv = fetch_neurovault(
            collection_id=5802,
            image_filter=image_filter,
            data_dir=data_dir,
            max_images=None
        )

    # Make directory if needed
    os.makedirs(data_dir, exist_ok=True)

    # Empty list for output files
    out_files = []

    # Extract and rename .nii.gz files into data_dir
    for gz_path, meta in zip(nv['images'], nv['images_meta']):
        cleaned_name = meta['name'].replace(" ", "-") + ".nii"
        output_path = os.path.join(data_dir, cleaned_name)

        with gzip.open(gz_path, 'rb') as f_in, open(output_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

        print(f"Extracted and saved: {cleaned_name}")

        out_files = out_files + [output_path,]

    # Remove temporary directory
    shutil.rmtree(os.path.join(data_dir,'neurovault'))

    # Split into two contrasts
    data_files = {}
    
    # Get data for first contrast
    for j in range(len(contrasts)):
        data_files[j] = [out_files[i] for i in range(len(out_files)) if contrasts[j].replace(' ','-') in out_files[i]]

    return data_files
