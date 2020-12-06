import tensorflow as tf
import numpy as np
from model import InpaitingModel
from dataset import Dataset
import os
import sys
import json

# folder = sys.argv[1]
job_folder = "job1"
with open(os.path.join(job_folder, 'configurations.json'), 'r') as f:
    config = json.load(f)
dataset_config = config["dataset_config"]
model_config = config["model_config"]
model_config["model_ckpoint_dir"] = os.path.join(job_folder, model_config["model_ckpoint_dir"])
dataset = Dataset(dataset_config, dataset_config["img_train_flist"], dataset_config["mask_train_flist"], training=True)
dataset = dataset.dataset.shuffle(100).batch(10).prefetch(200)
model = InpaitingModel(model_config)

# model.train_edge_part()