import sys
sys.path.append('../deep_text_detection')
sys.path.append('../single_shot_text_detection')

from matplotlib.image import imread
import os
import numpy as np
import cv2
import re
from PIL import Image
from collections import Counter
import requests

from inference import fetch_text_from_image
from inferencer.detector import find_text

def validate_user_exists(user_id, clientId='m06n3zljb7p21meoebwfyezt6nd992'):
    try:
        url = 'https://api.twitch.tv/kraken/users?id=' + user_id
        headers = {'Client-ID': clientId, 'Accept': 'application/vnd.twitchtv.v5+json'}
        r = requests.get(url, headers=headers).json()
        if r.get('_total') is not None and r.get('_total') != 0:
            return True
        else:
            return False
    except:
        return False
    
def return_user_info(user_id, clientId='m06n3zljb7p21meoebwfyezt6nd992'):
    url = 'https://api.twitch.tv/kraken/users?id=' + user_id
    headers = {'Client-ID': clientId, 'Accept': 'application/vnd.twitchtv.v5+json'}
    r = requests.get(url, headers=headers).json()
    return r['users']

def count_occurrences(lst, item):
    return len([item for curr in lst if curr == item])

def search_best_edge_enhancer(im, func, minimum_length=3, tolerance=4):
    if str(type(func)) != "<class 'function'>":
        print ("Empty function module, returning ...")
        return
    sigma_r_arr = np.arange(.1, 1.01, .1)
    sigma_s_arr = np.arange(20, 201, 20)
    all_predictions = list()
    
    for flag in [2, 1]:
        for sigma_s in sigma_s_arr:
            for sigma_r in sigma_r_arr:
                enhanced_strip = cv2.edgePreservingFilter(im, flags=flag, sigma_s=sigma_s, sigma_r=sigma_r)
                try:
                    predicted_text = func(enhanced_strip, correction=False)[0].strip()
                except:
                    continue
                predicted_text_numeric = re.sub('[^0-9]+', ' ', predicted_text).strip()
                
                for predicted_text_numeric_split in predicted_text_numeric.split(' '):
                    if len(predicted_text_numeric_split) >= minimum_length:
                        #print ("Count Occurrences = ", count_occurrences(all_predictions, predicted_text_numeric_split))
                        #print (all_predictions, predicted_text_numeric_split)
                        if count_occurrences(all_predictions, predicted_text_numeric_split) == tolerance-1:
                            return predicted_text_numeric_split
                        else:
                            #print ("Predicted Text Numeric: {}, {}".format(predicted_text_numeric_split,len(predicted_text_numeric_split)))
                            all_predictions.append(predicted_text_numeric_split)
    
    #print ("Came all the way to the end...")
    if len(all_predictions) == 0:
        return ''
    #print (all_predictions)
    return Counter(all_predictions).most_common()[0][0]

def search_best_detail_enhancer(im, func, minimum_length=3, tolerance=4):
    if str(type(func)) != "<class 'function'>":
        print ("Empty function module, returning ...")
        return
    sigma_r_arr = np.arange(.1, 1.01, .15)[::-1]
    sigma_s_arr = np.arange(60, 201, 25)[::-1]
    all_predictions = list()
    mapped_values = {}
    
    for sigma_s in sigma_s_arr:
        for sigma_r in sigma_r_arr:
            enhanced_strip = cv2.detailEnhance(im, sigma_s=sigma_s, sigma_r=sigma_r)
            try:
                predicted_text = func(enhanced_strip, correction=False)[0].strip()
            except:
                continue
            predicted_text_numeric = re.sub('[^0-9]+', ' ', predicted_text).strip()
            
            for predicted_text_numeric_split in predicted_text_numeric.split(' '):
                #print (count_occurrences(all_predictions, predicted_text_numeric_split))
                #print (all_predictions, predicted_text_numeric_split)
                if len(predicted_text_numeric_split) >= minimum_length:
                    if count_occurrences(all_predictions, predicted_text_numeric_split) == tolerance-1:
                        return predicted_text_numeric_split
                    else:
                        #print ("Predicted Text Numeric: {}, {}".format(predicted_text_numeric_split, len(predicted_text_numeric_split)))
                        all_predictions.append(predicted_text_numeric_split)
    
    #print ("Came all the way to the end...")
    if len(all_predictions) == 0:
        return ''
    #print (all_predictions, mapped_values)
    return Counter(all_predictions).most_common()[0][0]

def search_user_id(im:np.ndarray, abandon_search_length: int = 6, minimum_string_length: int = 3, 
                  advanced: str = False):
    boxes = find_text(im, boxes_only=True)
    weight = len(boxes)
    final_detected = []
    
    try:
        Image.fromarray(im)
    except:
        print ("Incompatible with present format, converting it to RGB ...")
        im = np.array(Image.fromarray((im * 255).astype(np.uint8)).resize((im.shape[0], im.shape[1])).convert('RGB'))

    for box in boxes:
        v_min, v_max = np.floor(np.min(box[:, 1])), np.floor(np.max(box[:, 1]))
        h_min, h_max = np.floor(np.min(box[:, 0])), np.floor(np.max(box[:, 0]))
        v_min, v_max, h_min, h_max = int(v_min-1), int(v_max-1), int(h_min-1), int(h_max-1)
        strip = im[v_min:v_max, h_min:h_max]
        
        try:
            early_detected = fetch_text_from_image(strip, correction=False)[0]
        except:
            continue
        #print ("Early Detected = ", early_detected)
        if validate_user_exists((re.sub('[^0-9]', ' ', early_detected)).strip()):
            return (re.sub('[^0-9]', ' ', early_detected)).strip()
        early_detected_alpha = re.sub('[^a-zA-Z]+', ' ', early_detected).strip().replace(' ', '')
        detected = ''
        if len(early_detected_alpha) >= abandon_search_length:
            continue
        else:
            # First apply edge enhancer
            detected = search_best_edge_enhancer(strip, fetch_text_from_image)
            if validate_user_exists(detected):
                return detected
            if len(detected) < minimum_string_length and advanced:
                # Search if detail enhancer can!
                detected_d_enhancr = search_best_detail_enhancer(strip, fetch_text_from_image)
                if validate_user_exists(detected_d_enhancr):
                    return detected
                if len(detected_d_enhancr) > len(detected):
                    detected = detected_d_enhancr
        if len(detected) >= minimum_string_length:
            final_detected.append((detected, weight))
        
        weight -= 1
    return final_detected

def extract_user_id(im):
    if type(im) != np.ndarray:
        im = imread(im)
    detected_ = search_user_id(im)
    if type(detected_) == str:
        return detected_, return_user_info(detected_)
    else:
        # Return the highest weight
        detected_sorted = sorted(detected_, key=lambda x: x[1], reverse=True)
        return detected_sorted[0][0], None