import time
import cv2
import numpy as np
import chainer
import glob
import os
from chainer import serializers, optimizers, Variable, cuda
import chainer.functions as F
from darknet19 import *
from lib.image_generator import *

# hyper parameters
input_height, input_width = (224, 224)
item_path = "./items"
background_path = "./backgrounds"
label_file = "./data/label.txt"
backup_path = "backup"
batch_size = 32
max_batches = 3000
learning_rate = 0.001
lr_decay_power = 4
momentum = 0.9
weight_decay = 0.0005

# load image generator
print("loading image generator...")
generator = ImageGenerator(item_path, background_path)

with open(label_file, "r") as f:
    labels = f.read().strip().split("\n")

# load model
print("loading model...")
model = Darknet19Predictor(Darknet19())
backup_file = "%s/backup.model" % (backup_path)
if os.path.isfile(backup_file):
    serializers.load_hdf5(backup_file, model) # load saved model
model.predictor.train = True

can_use_gpu = False
try:
    cuda.get_device(0).use()
    model.to_gpu() # for gpu
    can_use_gpu = True
except:
    # ignored
    pass

optimizer = optimizers.MomentumSGD(lr=learning_rate, momentum=momentum)
optimizer.use_cleargrads()
optimizer.setup(model)
optimizer.add_hook(chainer.optimizer.WeightDecay(weight_decay))

# - - -
# x, t = generator.generate_samples(
#     n_samples=batch_size,
#     n_items=1,
#     crop_width=input_width,
#     crop_height=input_height,
#     min_item_scale=0.3,
#     max_item_scale=1.3,
#     rand_angle=25,
#     minimum_crop=0.8,
#     delta_hue=0.01,
#     delta_sat_scale=0.5,
#     delta_val_scale=0.5
# )
# print(len(t), len(t[0]), len(t[0][0]), )
# for lb in t:
#     print(lb)
# print(x.shape)
# for yi in range(4):
#     for xi in range(8):
#         label_name = labels[t[yi*8 + xi][0]["label"]][:4]
#         import pylab
#         import numpy
#         img = x[yi*8 + xi].transpose(1, 2, 0) * 255
#         pylab.subplot(8, 8, yi * 8 * 2 + xi + 1)
#         pylab.imshow(img.astype(numpy.uint8))
#         pylab.axis("off")
#         pylab.title(label_name)
# pylab.show()
# - - -

# start to train
print("start training")
for batch in range(max_batches):
    # generate sample
    x, t = generator.generate_samples(
        n_samples=batch_size,
        n_items=1,
        crop_width=input_width,
        crop_height=input_height,
        min_item_scale=0.3,
        max_item_scale=1.3,
        rand_angle=25,
        minimum_crop=0.8,
        delta_hue=0.01,
        delta_sat_scale=0.5,
        delta_val_scale=0.5
    )
    x = Variable(x)
    one_hot_t = []
    for i in range(len(t)):
        one_hot_t.append(t[i][0]["one_hot_label"])
    if can_use_gpu:
        x.to_gpu()
    one_hot_t = np.array(one_hot_t, dtype=np.float32)
    one_hot_t = Variable(one_hot_t)
    if can_use_gpu:
        one_hot_t.to_gpu()

    y, loss, accuracy = model(x, one_hot_t)
    print("[batch %d (%d images)] learning rate: %f, loss: %f, accuracy: %f" % (batch+1, (batch+1) * batch_size, optimizer.lr, loss.data, accuracy.data))

    optimizer.zero_grads()
    loss.backward()

    optimizer.lr = learning_rate * (1 - batch / max_batches) ** lr_decay_power # Polynomial decay learning rate
    optimizer.update()

    # save model
    if (batch+1) % 1000 == 0:
        model_file = "%s/%s.model" % (backup_path, batch+1)
        print("saving model to %s" % (model_file))
        serializers.save_hdf5(model_file, model)
        serializers.save_hdf5(backup_file, model)

print("saving model to %s/darknet19_final.model" % (backup_path))
serializers.save_hdf5("%s/darknet19_final.model" % (backup_path), model)
import pickle
with open("darknet19_final_label.pkl", "wb") as f:
    pickle.dump(generator.labels)
