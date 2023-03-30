import sys
import logging
import numpy as np
import shutil
import pandas as pd

from pyflink.datastream import CheckpointingMode, StreamExecutionEnvironment
from pyflink.datastream.execution_mode import RuntimeExecutionMode

from modified_classifier import classifier
from modified_batch_inferrence import batch_inference
from modified_evaluation import generate_new_label, merged_stream
from modified_supervised_model import supervised_model
from modified_PLStream import unsupervised_stream
from train_model import InitialModelTrain
from utils import load_data

# logger
logger = logging.getLogger('PLStream')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('plstream.log', mode='w')
formatter = logging.Formatter('PLStream:%(thread)d %(lineno)d: %(levelname)s: %(asctime)s %(message)s',
                              datefmt='%m/%d/%Y %I:%M:%S %p', )
fh.setFormatter(formatter)
logger.addHandler(fh)

# supress warnings
np.warnings.filterwarnings('ignore', category=np.VisibleDeprecationWarning)

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout,
                        level=logging.INFO, format="%(message)s")

    parallelism = 1

    pseudo_data_folder = './senti_output'
    test_data_file = 'exp_test.csv'
    train_data_file = 'exp_train.csv'

    ## -------------------INITIAL TRAINING OF SUPERVISED MODEL------------------- ##

    df = pd.read_csv(train_data_file, names=['label', 'review'])
    df['label'] -= 1

    true_label = df.label
    yelp_review = df.review

    data_stream = []

    for i in range(len(yelp_review)):
        data_stream.append((int(true_label[i]), yelp_review[i]))

    InitialModelTrain(data_stream)

    print('Starting SentiStream...')
    print('===============================')

    new_df = pd.read_csv('train.csv', names=['label', 'review'])
    new_df['label'] -= 1

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    env.set_parallelism(1)
    env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)

    df = new_df[:1000]

    ## -------------------GENERATE PSEUDO-LABEL FROM BOTH LEARNING METHODS------------------- ##
    true_label = df.label
    yelp_review = df.review

    data_stream = []

    for i in range(len(yelp_review)):
        data_stream.append((i, int(true_label[i]), yelp_review[i]))

    # env.set_parallelism(1)
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)

    ds = env.from_collection(collection=data_stream)

    print("unsupervised stream,classifier and evaluation")

    ds1 = unsupervised_stream(ds)
    ds2 = classifier(ds)

    ds = merged_stream(ds1, ds2)
    ds = generate_new_label(ds)

    ## -------------------SUPERVISED MODEL INFERENCE------------------- ##

    print("batch_inference")

    # # env.set_parallelism(1)

    env.set_runtime_mode(RuntimeExecutionMode.BATCH)

    acc = batch_inference(ds)
    acc.print()

    # ## -------------------SUPERVISED MODEL TRAIN-------------------##
    # print("supervised_model_train")

    # # train model on pseudo data with supervised mode
    # pseudo_data_size, train_df = load_data(
    #     pseudo_data_folder, train_data_file)

    # true_label = df.label
    # yelp_review = df.review

    # data_stream = []

    # for i in range(len(yelp_review)):
    #     data_stream.append((int(true_label[i]), yelp_review[i]))

    # ds = env.from_collection(collection=data_stream)

    # supervised_model(ds, parallelism, len(train_df), pseudo_data_size, 0.4,
    #                  pseudo_data_collection_threshold=0.0, accuracy_threshold=0.9)  # change accc

    # supervised_model(ds, parallelism,
    #                  pseudo_data_collection_threshold=0.0, accuracy_threshold=0.9)  # change accc

    env.execute()

    # shutil.rmtree('senti_output', ignore_errors=False, onerror=None)
