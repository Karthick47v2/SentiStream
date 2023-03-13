#!/usr/bin/env python3
import numpy as np

from pyflink.datastream.execution_mode import RuntimeExecutionMode

from modified_batch_inferrence import batch_inference
from modified_evaluation import generate_new_label, merged_stream
# from supervised_model import supervised_model
from utils import load_data

np.warnings.filterwarnings('ignore', category=np.VisibleDeprecationWarning)

import logging
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream import CheckpointingMode
import pandas as pd
import sys
from modified_PLStream import unsupervised_stream
from dummy_classifier import dummy_classifier

logger = logging.getLogger('PLStream')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('plstream.log', mode='w')
formatter = logging.Formatter('PLStream:%(thread)d %(lineno)d: %(levelname)s: %(asctime)s %(message)s',
                              datefmt='%m/%d/%Y %I:%M:%S %p', )
fh.setFormatter(formatter)
logger.addHandler(fh)

PSEUDO_DATA_COLLECTION_THRESHOLD = 0
ACCURACY_THRESHOLD = 0.9
parallelism = 1
train_data_size = 0

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")

    input_path = 'exp_test.csv'
    df = pd.read_csv('exp_train.csv', names=['label', 'review'])
    df['label'] -= 1

    # # train initial supervised model
    # supervised_model(parallelism, df, len(df), 0, 0, 0, 0, init=True)

    true_label = df.label
    yelp_review = df.review

    data_stream = []

    for i in range(len(yelp_review)):
        data_stream.append((i, int(true_label[i]), yelp_review[i]))

    # env = StreamExecutionEnvironment.get_execution_environment()
    # env.set_parallelism(1)
    # env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)
    # ds = env.from_collection(collection=data_stream)

    # print("unsupervised stream,classifier and evaluation")
    # print('Coming Stream is ready...')
    # print('===============================')

    # # data stream functions
    # ds1 = unsupervised_stream(ds)
    # ds2 = dummy_classifier(ds)
    # ds = merged_stream(ds1, ds2)
    # ds = generate_new_label(ds)
    # env.execute()

    # print("Finished running datastream")

    ####### Run supersied part of sentistream on batch mode

    # data source for batch_inferrence and supervised_model
    pseudo_data_folder = './senti_output'
    test_data_file = './exp_test.csv'
    train_data_file = './exp_train.csv'

    # data sets prep
    pseudo_data_size, test_df = load_data(pseudo_data_folder, test_data_file)

    test_data_size = len(test_df)

    true_label = test_df.label
    yelp_review = test_df.review

    data_stream = []

    for i in range(len(yelp_review)):
        data_stream.append((int(true_label[i]), yelp_review[i]))

    print("batch_inference")
    print('Coming Stream is ready...')
    print('===============================')

    # batch stream set up
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.BATCH)
    env.set_parallelism(1)
    env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)

    ds = env.from_collection(collection=data_stream)
    accuracy = batch_inference(ds, test_data_size)
    print(accuracy)

    # print("supervised_model_train")

    # # train model on pseudo data with supervised mode
    # pseudo_data_size, train_df = load_and_augment_data(pseudo_data_folder, train_data_file)
    # train_data_size = len(train_df)

    # supervised_model(parallelism, train_df, train_data_size, pseudo_data_size, PSEUDO_DATA_COLLECTION_THRESHOLD,
    #                  accuracy,
    #                  ACCURACY_THRESHOLD)