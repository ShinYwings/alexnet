import tensorflow as tf 
import numpy as np
import os
import sys
import model2 as model
import time
import data_augmentation as da
from datetime import datetime as dt
from matplotlib import pyplot as plt
import optimizer_alexnet
import cv2
import multiprocessing
import progressbar
import math
# import sklearn
# from image_plotting import plot_confusion_matrix
# from image_plotting import plot_to_image

# Hyper parameters
# TODO : argparse?
LEARNING_RATE = 1e-2
NUM_EPOCHS = 90
NUM_CLASSES = 1000    # IMAGENET 2012
MOMENTUM = 0.9 # SGD + MOMENTUM
BATCH_SIZE = 128

DATASET_DIR = r"D:\ILSVRC2012"

# 본 게임
TRAIN_TFRECORD_DIR = r"D:\ILSVRC2012\ILSVRC2012_tfrecord_train"
TEST_TFRECORD_DIR = r"D:\ILSVRC2012\ILSVRC2012_tfrecord_val"

# ?
SAMPLE4_TRAIN_TFRECORD_DIR = r"D:\ILSVRC2012\300000_tfrecord_train"

# 학습 실험용
SAMPLE_TRAIN_TFRECORD_DIR = r"D:\ILSVRC2012\sample_tfrecord_train"
SAMPLE_TEST_TFRECORD_DIR = r"D:\ILSVRC2012\sample_tfrecord_val"

SAMPLE2_TRAIN_TFRECORD_DIR = r"D:\ILSVRC2012\20000_tfrecord_train"
SAMPLE2_TEST_TFRECORD_DIR = r"D:\ILSVRC2012\5000_tfrecord_val"

SAMPLE3_TRAIN_TFRECORD_DIR = r"D:\ILSVRC2012\20000_q95_tfrecord_train"
SAMPLE3_TEST_TFRECORD_DIR = r"D:\ILSVRC2012\5000_q95_tfrecord_val"

# 함수 실험용
FUNCTEST_TRAIN_TFRECORD_DIR = r"D:\ILSVRC2012\functest_tfrecord_train"
FUNCTEST_TEST_TFRECORD_DIR = r"D:\ILSVRC2012\functest_tfrecord_val"

# Input으로 넣을 데이터 선택
RUN_TRAIN_DATASET = SAMPLE4_TRAIN_TFRECORD_DIR
RUN_TEST_DATASET = TEST_TFRECORD_DIR

LRN_INFO = (5, 1e-4, 0.75, 2) # radius, alpha, beta, bias   # hands-on 에서는 r=2 a = 0.00002, b = 0.75, k =1 이라고 되어있음...
INPUT_IMAGE_SIZE = 227 #WIDTH, HEIGHT    # cropped by 256x256 images
WEIGHT_DECAY = 5e-4

# Fixed
IMAGENET_MEAN = [122.10927936917298, 116.5416959998387, 102.61744377213829] # rgb format
DROUPUT_PROP = 0.5
ENCODING_STYLE = "utf-8"
AUTO = tf.data.experimental.AUTOTUNE

widgets = [' [', 
         progressbar.Timer(format= 'elapsed time: %(elapsed)s'), 
         '] ', 
           progressbar.Bar('/'),' (', 
           progressbar.ETA(), ') ', 
          ] 

def image_cropping(image , training = None):  # do it only in test time
    
    global INPUT_IMAGE_SIZE

    cropped_images = list()

    if training:

        # TODO intend image 수정 필요
        intend_image = tf.cast(image, tf.float32)
        # intend_image = da.intensity_RGB(image=image)
        
        horizental_fliped_image = tf.image.flip_left_right(intend_image)

        ran_crop_image1 = tf.image.random_crop(intend_image,size=[INPUT_IMAGE_SIZE, INPUT_IMAGE_SIZE, 3])
        ran_crop_image2 = tf.image.random_crop(horizental_fliped_image,
                                    size=[INPUT_IMAGE_SIZE, INPUT_IMAGE_SIZE, 3])

        cropped_images.append(tf.subtract(ran_crop_image1, IMAGENET_MEAN))
        cropped_images.append(tf.subtract(ran_crop_image2, IMAGENET_MEAN))
        
    else:
        
        horizental_fliped_image = tf.image.flip_left_right(image)
        # for original image
        topleft = tf.cast(image[:227,:227], dtype=tf.float32)
        topright = tf.cast(image[29:,:227], dtype=tf.float32)
        bottomleft = tf.cast(image[:227,29:], dtype=tf.float32)
        bottomright = tf.cast(image[29:,29:], dtype=tf.float32)
        center = tf.cast(image[15:242, 15:242], dtype=tf.float32)

        cropped_images.append(tf.subtract(topleft, IMAGENET_MEAN))
        cropped_images.append(tf.subtract(topright, IMAGENET_MEAN))
        cropped_images.append(tf.subtract(bottomleft, IMAGENET_MEAN))
        cropped_images.append(tf.subtract(bottomright, IMAGENET_MEAN))
        cropped_images.append(tf.subtract(center, IMAGENET_MEAN))
        
        # # for horizental_fliped_image
        # horizental_fliped_image_topleft = tf.cast(horizental_fliped_image[:227,:227], dtype=tf.float32)
        # horizental_fliped_image_topright = tf.cast(horizental_fliped_image[29:,:227], dtype=tf.float32)
        # horizental_fliped_image_bottomleft = tf.cast(horizental_fliped_image[:227,29:], dtype=tf.float32)
        # horizental_fliped_image_bottomright = tf.cast(horizental_fliped_image[29:,29:], dtype=tf.float32)
        # horizental_fliped_image_center = tf.cast(horizental_fliped_image[15:242, 15:242], dtype=tf.float32)

        # cropped_images.append(tf.subtract(horizental_fliped_image_topleft, IMAGENET_MEAN))
        # cropped_images.append(tf.subtract(horizental_fliped_image_topright, IMAGENET_MEAN))
        # cropped_images.append(tf.subtract(horizental_fliped_image_bottomleft, IMAGENET_MEAN))
        # cropped_images.append(tf.subtract(horizental_fliped_image_bottomright, IMAGENET_MEAN))
        # cropped_images.append(tf.subtract(horizental_fliped_image_center, IMAGENET_MEAN))
    return cropped_images

def get_logdir(root_logdir):
    run_id = dt.now().strftime("run_%Y_%m_%d-%H_%M_%S")
    
    return os.path.join(root_logdir, run_id)

def _parse_function(example_proto):
    # Parse the input `tf.train.Example` proto using the dictionary above.
    feature_description = {
        'image': tf.io.FixedLenFeature([], tf.string),
        'label': tf.io.FixedLenFeature([], tf.int64),
    }
    example = tf.io.parse_single_example(example_proto, feature_description)

    # images = tf.image.decode_jpeg(example['image'], channels=3)
    # images = images[15:242, 15:242, :]
    # images = tf.cast(images, tf.float32)
    # images = tf.subtract(images, IMAGENET_MEAN)

    # raw_labels = tf.cast(example['label'], tf.int32)
    # labels = tf.subtract(raw_labels, 1)
    # print(labels)
    # labels = tf.one_hot(labels, 1000)

    return example

if __name__ == "__main__":

    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    
    root_dir=os.getcwd()
    dataset_dir=os.path.abspath(DATASET_DIR)
    sys.path.append(root_dir)
    sys.path.append(dataset_dir)

    """Path for tf.summary.FileWriter and to store model checkpoints"""
    filewriter_path = os.path.join(root_dir, "tensorboard")
    checkpoint_path = os.path.join(root_dir, "checkpoints")

    """Create parent path if it doesn't exist"""
    if not os.path.isdir(checkpoint_path):
        os.mkdir(checkpoint_path)

    if not os.path.isdir(filewriter_path):
        os.mkdir(filewriter_path)
    
    root_logdir = os.path.join(filewriter_path, "logs\\fit\\")
    logdir = get_logdir(root_logdir)
    train_logdir = os.path.join(logdir, "train\\")
    val_logdir = os.path.join(logdir, "val\\") 

    train_tfrecord_list = list()
    test_tfrecord_list = list()

    train_dirs = os.listdir(RUN_TRAIN_DATASET)
    test_dirs = os.listdir(RUN_TEST_DATASET)
    
    for train_dir in train_dirs:
        dir_path = os.path.join(RUN_TRAIN_DATASET, train_dir)
        a =tf.data.Dataset.list_files(os.path.join(dir_path, '*.tfrecord'))
        train_tfrecord_list.extend(a)
    
    for test_dir in test_dirs:
        dir_path = os.path.join(RUN_TEST_DATASET, test_dir)
        b = tf.data.Dataset.list_files(os.path.join(dir_path, '*.tfrecord'))
        test_tfrecord_list.extend(b)

    train_buf_size = len(train_tfrecord_list)
    test_buf_size= len(test_tfrecord_list)
    print("train_buf_size", train_buf_size)
    print("test_buf_size", test_buf_size)
    train_ds = tf.data.TFRecordDataset(filenames=train_tfrecord_list, num_parallel_reads=AUTO, compression_type="GZIP")
    test_ds = tf.data.TFRecordDataset(filenames=test_tfrecord_list, num_parallel_reads=AUTO, compression_type="GZIP")
    # train_ds = train_ds.shuffle(buffer_size=train_buf_size)
    # test_ds = test_ds.shuffle(buffer_size=test_buf_size)
    train_ds = train_ds.map(_parse_function, num_parallel_calls=AUTO)
    test_ds = test_ds.map(_parse_function, num_parallel_calls=AUTO)
    train_ds = train_ds.batch(batch_size=BATCH_SIZE, drop_remainder=False).prefetch(AUTO)
    test_ds = test_ds.batch(batch_size=BATCH_SIZE, drop_remainder=False).prefetch(AUTO)
    
    
    """check images are all right"""
    
    # plt.figure(figsize=(20,20))

    # for i, (image,_) in enumerate(train_ds.take(5)):
    #     ax = plt.subplot(5,5,i+1)
    #     plt.imshow(image[i])
    #     plt.axis('off')
    # plt.show()

    """
    Input Pipeline
    
    experimental: API for input pipelines
    cardinality: size of a set
        > in DB, 중복도가 낮으면 카디널리티가 높다. 중복도가 높으면 카디널리티가 낮다.
    """
    """
    [3 primary operations]
        1. Preprocessing the data within the dataset
        2. Shuffle the dataset
        3. Batch data within the dataset
    
    drop_ramainder: 주어진 dataset을 batch_size 나눠주고 
                    batch_size 만족 못하는 나머지들을 남길지 버릴지
    
    shuffle: Avoid local minima에 좋음
    
    prefetch(1): 데이터셋은 항상 한 배치가 미리 준비되도록 최선을 다합니다.
                 훈련 알고리즘이 한 배치로 작업을 하는 동안 이 데이터셋이 동시에 다음 배치를 준비
                 합니다. (디스크에서 데이터를 읽고 전처리)
    """
    # train_tensorboard = tf.keras.callbacks.TensorBoard(log_dir=train_logdir)
    # test_tensorboard = tf.keras.callbacks.TensorBoard(log_dir=val_logdir)
    _model = model.mAlexNet(INPUT_IMAGE_SIZE, LRN_INFO, NUM_CLASSES)
    loss_object = tf.keras.losses.SparseCategoricalCrossentropy()

    # learning_rate_fn = optimizer_alexnet.AlexNetLRSchedule(initial_learning_rate = LEARNING_RATE, name="performance_lr")
    # _optimizer = optimizer_alexnet.AlexSGD(learning_rate=learning_rate_fn, momentum=MOMENTUM, weight_decay=WEIGHT_DECAY, name="alexnetOp")
    _optimizer = tf.keras.optimizers.Adam()
    # 모델의 손실과 성능을 측정할 지표, 에포크가 진행되는 동안 수집된 측정 지표를 바탕으로 결과 출력
    train_loss = tf.keras.metrics.Mean(name= 'train_loss', dtype=tf.float32)
    train_accuracy = tf.keras.metrics.SparseCategoricalAccuracy(name='train_accuracy')
    test_loss = tf.keras.metrics.Mean(name='test_loss', dtype=tf.float32)
    test_accuracy = tf.keras.metrics.SparseCategoricalAccuracy(name='test_accuracy')
    prev_test_accuracy = -1.

    # _model.compile(optimizer=_optimizer, loss=loss_object, metrics=['accuracy'])
    # _model.fit(train_ds,batch_size=BATCH_SIZE, workers=8, use_multiprocessing=True, epochs=NUM_EPOCHS, callbacks=[train_tensorboard])
    # _model.summary()
    # _model.evaluate(test_ds,batch_size=BATCH_SIZE,workers=8, use_multiprocessing=True, verbose=2, callbacks=[test_tensorboard])
    # NaN 발생이유 LR이 너무 높거나, 나쁜 초기화...
    """
    Tensorboard

    monitoring
        - training loss
        - training accurarcy
        - validation loss
        - validation accuracy

    get_logdir: return the location of the exact directory that is named
                    according to the current time the training phase starts
    """

    """
    Training and Results

    To train the network, we have to compile it.

    Compilation processes
        - Loss function
        - Optimization Algorithm
        - Learning Rate
    """
    
    train_summary_writer = tf.summary.create_file_writer(train_logdir)
    val_summary_writer = tf.summary.create_file_writer(val_logdir)
    
    print('tensorboard --logdir={}'.format(logdir))

    # prev_test_accuracy = tf.Variable(-1., trainable = False)

    with tf.device('/GPU:1'):
        @tf.function
        def train_step(images, labels):

            with tf.GradientTape() as tape:

                predictions = _model(images, training = True)
                loss = loss_object(labels, predictions)

            gradients = tape.gradient(loss, _model.trainable_variables)
            #apply gradients 가 v1의 minimize를 대체함
            _optimizer.apply_gradients(zip(gradients, _model.trainable_variables))

            train_loss(loss)
            train_accuracy(labels, predictions)
            
        @tf.function
        def test_step(test_images, test_labels):
            test_predictions = _model(test_images, training =False)
            t_loss = loss_object(test_labels, test_predictions)

            test_loss(t_loss)
            test_accuracy(test_labels, test_predictions)
            # tf.cond(tf.less_equal(test_accuracy.result(),prev_test_accuracy.read_value()),
            #     learning_rate_fn.cnt_up_num_of_statinary_loss,
            #     lambda: None)
            # prev_test_accuracy.assign(test_accuracy.result())

            
            # cm = sklearn.metrics.confusion_matrix(test_labels, test_predictions)
            # figure = plot_confusion_matrix(cm, class_names=test_labels)
            # cm_image = plot_to_image(figure)

            # with train_summary_writer.as_default():
            #     tf.summary.image("Confusion Matrix", cm_image, step=epoch)
        
    #     def performance_lr_scheduling():
    #         learning_rate_fn.cnt_up_num_of_statinary_loss()
    # p = multiprocessing.Pool(CPU_CORE)

    print("시작")
    for epoch in range(NUM_EPOCHS):

        train_loss.reset_states()
        test_loss.reset_states()
        train_accuracy.reset_states()
        test_accuracy.reset_states()

        start = time.perf_counter()
        bar = progressbar.ProgressBar(max_value= math.ceil(train_buf_size/128.), widgets=widgets)
        test_bar = progressbar.ProgressBar(max_value= math.ceil(test_buf_size/128.), widgets=widgets)
        bar.start()
        test_bar.start()
        for step, tb in enumerate(train_ds):
            
            raw_images= tb['image'].numpy()
            raw_labels= tb['label'].numpy()
            
            images= list()
            labels = list()

            for i in range(0,len(raw_labels)):

                image = tf.image.decode_jpeg(raw_images[i], channels=3)
                label = tf.cast(raw_labels[i]-1, tf.int32)
                # label = tf.one_hot(label, 1000)
                # TODO with cpu 멀티프로세싱 해주기
                cropped_intend_image = image_cropping(image, training=True)

                for j in cropped_intend_image:
                    
                    images.append(j)
                    labels.append(label)

            images = tf.stack(images)
            labels = tf.stack(labels)
            
            train_batch_ds = tf.data.Dataset.from_tensor_slices((images, labels))
            train_batch_ds = train_batch_ds.shuffle(buffer_size=len(labels)).batch(batch_size=BATCH_SIZE, drop_remainder=True).prefetch(AUTO)
            
            for batch_size_images, batch_size_labels in train_batch_ds:

                train_step(batch_size_images, batch_size_labels)

            bar.update(step)

        with train_summary_writer.as_default():
            tf.summary.scalar('loss', train_loss.result(), step=epoch+1)
            tf.summary.scalar('accuracy', train_accuracy.result()*100, step=epoch+1)

        for step, tc in enumerate(test_ds):
            test_raw_images= tc['image'].numpy()
            test_raw_labels= tc['label'].numpy()
            
            test_images = list()
            test_labels = list()

            for i in range(0,len(test_raw_labels)):
                test_image = tf.image.decode_jpeg(test_raw_images[i], channels=3)
                test_label = tf.cast(test_raw_labels[i]-1, tf.int32)
                # test_label = tf.one_hot(test_label, 1000)
                # cropped_image= p.starmap(image_cropping, [(image, False)])
                
                # TODO with cpu 멀티프로세싱 해주기
                test_cropped_image = image_cropping(test_image, training = False)
                
                for k in test_cropped_image:
                    test_images.append(k)
                    test_labels.append(test_label)

            test_images = tf.stack(test_images)
            test_labels = tf.stack(test_labels)

            #####
            test_batch_ds = tf.data.Dataset.from_tensor_slices((test_images, test_labels))
            test_batch_ds = test_batch_ds.shuffle(buffer_size=len(test_labels)).batch(batch_size=BATCH_SIZE, drop_remainder=True).prefetch(AUTO)
            
            for batch_size_images, batch_size_labels in test_batch_ds:
                test_step(batch_size_images, batch_size_labels)
            ####
            test_bar.update(step)
        
        with val_summary_writer.as_default():
            tf.summary.scalar('loss', test_loss.result(), step=epoch+1)
            tf.summary.scalar('accuracy', test_accuracy.result()*100, step=epoch+1)
        print('Epoch: {}, Loss: {}, Accuracy: {}, Test Loss: {}, Test Accuracy: {}'.format(epoch+1,train_loss.result(),
                            train_accuracy.result()*100, test_loss.result(),test_accuracy.result()*100))
        
        print("Spends time({}) in Epoch {}".format(epoch+1, time.perf_counter() - start))

        # if prev_test_accuracy >= test_accuracy.result():
        #     performance_lr_scheduling()
        # prev_test_accuracy = test_accuracy.result()

        
        
    print("끝")