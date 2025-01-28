# Copyright (C) 2021-2022 Intel Corporation
#
# SPDX-License-Identifier: MIT


import os
import argparse
import logging
from glob import glob

import numpy as np
from tqdm import tqdm
from PIL import Image
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space
from matplotlib import pyplot as plt


TAG_SLOPE = (0x0028, 0x1053)
TAG_INTERSEPT =  (0x0028, 0x1052)
TAG_INSTANCE_NUMBER = (0x0020,0x0013)


# Script configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
parser = argparse.ArgumentParser(
    description="The script is used to convert some kinds of DICOM (.dcm) files to regular image files (.png)"
)
parser.add_argument(
    "--input",
    type=str,
    help="A root directory with medical data files in DICOM format. The script finds all these files based on their extension",
)
parser.add_argument(
    "--output",
    type=str,
    help="Where to save converted files. The script repeats internal directories structure of the input root directory",
)
parser.add_argument(
    "--window_centre",
    type=int,
    required=False,
    help="Window Center",
)
parser.add_argument(
    "--window_length",
    type=int,
    required=False,   
    help="Window Length",
)
args = parser.parse_args()


class Converter:
    def __init__(self, filename, window_centre, window_length):
        with dcmread(filename) as ds:
            self._pixel_array = ds.pixel_array.astype(np.int16)
            self._photometric_interpretation = ds.PhotometricInterpretation
            self._min_value = ds.pixel_array.min()
            self._max_value = ds.pixel_array.max()
            self.slope = self.read_tag(ds, TAG_SLOPE)#ds[TAG_SLOPE].value
            self.intersept = self.read_tag(ds, TAG_INTERSEPT)#ds[TAG_INTERSEPT].value
            self.instance_number = self.read_tag(ds, TAG_INSTANCE_NUMBER)#ds[TAG_INSTANCE_NUMBER].value 
            self._depth = 16#ds.BitsStored

            self.window_centre = window_centre
            self.window_length = window_length
            print(self.slope, self.intersept, self.instance_number)
            
      

            logging.debug("File: {}".format(filename))
            logging.debug("Photometric interpretation: {}".format(self._photometric_interpretation))
            logging.debug("Min value: {}".format(self._min_value))
            logging.debug("Max value: {}".format(self._max_value))
            logging.debug("Depth: {}".format(self._depth))

            try:
                self._length = ds["NumberOfFrames"].value
            except KeyError:
                self._length = 1

    def read_tag(self, ds, name_tag):
        if name_tag in ds:
            tag = ds[name_tag].value
        else:
            tag = None
        return tag

    def window_image(self, img, window_center, window_width, intersept = 0, slope = 1, rescale = True):#, intercept, slope, rescale=True):
            img = (img * slope + intersept) #for translation adjustments given in the dicom file. 
            img_min = window_center - window_width//2 #minimum HU level
            img_max = window_center + window_width//2 #maximum HU level
            img[img < img_min] = img_min #set img_min for all HU levels less than minimum HU level
            img[img > img_max] = img_max #set img_max for all HU levels higher than maximum HU level
            if rescale: 
                img = (img - img_min) / (img_max - img_min) * 255.0 
            img = img.astype(np.uint8)
            return img            

    def __len__(self):
        return self._length

    def __iter__(self):
        if self._length == 1:
            self._pixel_array = np.expand_dims(self._pixel_array, axis=0)

        for pixel_array in self._pixel_array:
            print(self.window_centre)
            if self.window_centre and self.window_length and  self.intersept and self.slope:
             
                pixel_array = self.window_image(pixel_array, self.window_centre, self.window_length, self.intersept, self.slope)
                pixel_array = pixel_array.astype(np.uint8)
                image = Image.fromarray(pixel_array.astype(np.uint8))
            else:
                # Normalization to an output range 0..255, 0..65535
                pixel_array = pixel_array - self._min_value
                pixel_array = pixel_array.astype(int) * (2**self._depth - 1)
                pixel_array = pixel_array // (self._max_value - self._min_value)
                if self._depth == 8:
                    image = Image.fromarray(pixel_array.astype(np.uint8))
                elif self._depth == 16:
                    image = Image.fromarray(pixel_array.astype(np.uint16))
                else:
                    raise Exception("Not supported depth {}".format(self._depth))
            
                

            yield image


def main(root_dir, output_root_dir, window_centre, window_length):
    dicom_files = glob(os.path.join(root_dir, "**", "*.dcm"), recursive=True)
    if not len(dicom_files):
        logging.info("DICOM files are not found under the specified path")
    else:
        logging.info("Number of found DICOM files: " + str(len(dicom_files)))

    pbar = tqdm(dicom_files)
    for input_filename in pbar:
        pbar.set_description("Conversion: " + input_filename)
        input_basename = os.path.basename(input_filename)
        #print(input_basename)

        output_subpath = os.path.relpath(os.path.dirname(input_filename), root_dir)
        output_path = os.path.join(output_root_dir, output_subpath)
        output_basename = "{}.png".format(os.path.splitext(input_basename)[0])
        output_filename = os.path.join(output_path, output_basename)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        try:
            iterated_converter = Converter(input_filename, window_centre, window_length)
            length = len(iterated_converter)
            for i, image in enumerate(iterated_converter):
                # if length == 1:
                #     image.save(output_filename)
                # else:
                if iterated_converter.instance_number:
                    number = iterated_converter.instance_number
                else:
                    number = i    
                #filename_index = str(number).zfill(len(str(length)))
                filename_index = str(number).zfill(3)
                list_output_filename = os.path.join(output_root_dir, "{}_{}.png".format(filename_index,
                    os.path.splitext(input_basename)[0]
                ))
                print(f"saving {list_output_filename}")
                image.save(list_output_filename)

        except Exception as ex:
            logging.error("Error while processing " + input_filename)
            logging.error(ex)
        #break

if __name__ == "__main__":
    input_root_path = os.path.abspath(args.input.rstrip(os.sep))
    output_root_path = os.path.abspath(args.output.rstrip(os.sep))
    window_centre = args.window_centre
    window_length = args.window_length

    logging.info("From: {}".format(input_root_path))
    logging.info("To: {}".format(output_root_path))
    main(input_root_path, output_root_path,  window_centre,  window_length)
