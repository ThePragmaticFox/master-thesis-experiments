#!/bin/python3

# local imports
import helper
import IK_2d_two_linkage as experiment
#import IK_3d_three_linkage as experiment

# other imports
import os
import sys
import time
import shutil
import random
import pathlib
import datetime

import torch
import numpy as np

from torch.utils.tensorboard import SummaryWriter

# is needed for torch.use_deterministic_algorithms(True) below
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

random.seed(helper.SEED_DICT["bench_random_seed"])
np.random.seed(helper.SEED_DICT["bench_numpy_random_seed"])
torch.manual_seed(helper.SEED_DICT["bench_torch_random_seed"])
torch.use_deterministic_algorithms(True)
torch.backends.cudnn.benchmark = False
# torch.autograd.set_detect_anomaly(True)

print(f"PyTorch Version: {torch.__version__}")
print(f"NumPy Version: {np.version.version}")
print(f"Matplotlib Version: {experiment.matplotlib.__version__}")

torch.set_default_dtype(helper.DTYPE_TORCH)

IS_ONLY_PLOT_REGION = False

# 0 is sampling once N_SAMPLES_TRAIN at the beginning of training
# 1 is resampling N_SAMPLES_TRAIN after each iteration
# 2 is expansion sampling: sampling once N_SAMPLES_TRAIN, but start with 1 sample, then add more and more samples from the vicinity.

SAMPLING_MODE = 1
N_SAMPLES_TRAIN = 1000

# those two only trigger if the requirements are met
IS_MODE_2_ABLATION = False
IS_TWOLINKAGE_CONSTRAINED = False

N_ITERATIONS = 10000

if "exp_SAMPLING_MODE" in globals() :

    SAMPLING_MODE = globals()["exp_SAMPLING_MODE"]

if "exp_N_SAMPLES_TRAIN" in globals() :

    N_SAMPLES_TRAIN = globals()["exp_N_SAMPLES_TRAIN"]

if "exp_IS_MODE_2_ABLATION" in globals() :

    IS_MODE_2_ABLATION = globals()["exp_IS_MODE_2_ABLATION"]

if "exp_IS_TWOLINKAGE_CONSTRAINED" in globals() :

    IS_TWOLINKAGE_CONSTRAINED = globals()["exp_IS_TWOLINKAGE_CONSTRAINED"]

if "exp_N_ITERATIONS" in globals() :

    N_ITERATIONS = globals()["exp_N_ITERATIONS"]

# not needed for anything else
if IS_MODE_2_ABLATION and SAMPLING_MODE != 2:
    IS_MODE_2_ABLATION = False
if IS_TWOLINKAGE_CONSTRAINED and experiment.identifier_string != "IK_2d":
    IS_TWOLINKAGE_CONSTRAINED = False

directory_path = pathlib.Path(pathlib.Path(
    __file__).parent.resolve(), "experiments")
dir_path_id_partial = pathlib.Path(
    directory_path, experiment.identifier_string)

dtstring = str(datetime.datetime.now().replace(microsecond=0))
char_replace = [' ', '-', ':']
for c in char_replace:
    dtstring = dtstring.replace(c, '_')

mode_str = str(SAMPLING_MODE)

if IS_TWOLINKAGE_CONSTRAINED:

    mode_str += "c"

if IS_MODE_2_ABLATION:

    mode_str += "a"

iter_str = ""

if N_ITERATIONS == 10000:
    iter_str = "10k"

if N_ITERATIONS == 20000:
    iter_str = "20k"

if N_ITERATIONS == 25000:
    iter_str = "25k"

if N_ITERATIONS == 50000:
    iter_str = "50k"

if N_ITERATIONS == 100000:
    iter_str = "100k"

exp_type_str = f"Samples_{N_SAMPLES_TRAIN}_Mode_{mode_str}_Iterations_{iter_str}"

dir_path_id = pathlib.Path(dir_path_id_partial, experiment.identifier_string + "_" + exp_type_str + "_" + dtstring)
dir_path_id_model = pathlib.Path(dir_path_id, "model")
dir_path_id_plots = pathlib.Path(dir_path_id, "plots")

# order matters for directory creation
directories = [
    directory_path,
    dir_path_id_partial,
    dir_path_id,
    dir_path_id_model,
    dir_path_id_plots
]

txt_dict = {
    'iteration': '',
    'lr': '',
    'mean': '',
    'stddev': '',
    'min': '',
    'max': '',
    'median': '',
    '75percentile': '',
    '90percentile': '',
    '95percentile': '',
    '99percentile': ''
}

N_SAMPLES_VAL = 10000
N_SAMPLES_TEST = 100000

N_SAMPLES_THETA = 100000

helper.TIME_MEASURE_UPDATE = N_ITERATIONS // 100
helper.TENSORBOARD_UPDATE = N_ITERATIONS // 100

NN_DIM_IN = 1*experiment.N_DIM_X_STATE
NN_DIM_OUT = 2*experiment.N_DIM_THETA*experiment.N_TRAJOPT
NN_DIM_IN_TO_OUT = 256

LR_INITIAL = 1e-2

LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_1 = 0.99930
LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_2 = 0.99930

#LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_1 = 0.999925
#LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_2 = 0.9988#0.9973

if N_ITERATIONS == 100000 :

    LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_1 = 0.999925
    LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_2 = 0.999925

# parameters for mode 1
MODE_1_MODULO_FACTOR = 1

# parameters for mode 2
DIVISOR = 3.0
TENTH = 0.1 * N_ITERATIONS


class Model(torch.nn.Module):

    def mish(self, x):

        return x * torch.tanh_(torch.log(1.0 + torch.exp(x)))

    def __init__(self):

        super(Model, self).__init__()

        self.fc_start_1 = torch.nn.Linear(NN_DIM_IN, 1*NN_DIM_IN_TO_OUT)

        self.fc_middle = torch.nn.Linear(
            1*NN_DIM_IN_TO_OUT, 1*NN_DIM_IN_TO_OUT)

        self.fc_end = torch.nn.Linear(NN_DIM_IN_TO_OUT, NN_DIM_OUT)
        self.fc_end_alt = torch.nn.Linear(NN_DIM_IN_TO_OUT, NN_DIM_OUT // 2)

        self.act = None

        if "exp_activation_function" in globals() :

            exp_activation_function = globals()["exp_activation_function"]

            print("Activation Function Used: ")
            print(exp_activation_function)
            print()

            if exp_activation_function == "cos" :

                self.act = torch.cos

            if exp_activation_function == "sin" :

                self.act = torch.sin

            if exp_activation_function == "mish" :

                self.act = self.mish

            if exp_activation_function == "sigmoid" :

                self.act = torch.nn.Sigmoid()

            if exp_activation_function == "tanh" :

                self.act = torch.nn.Tanh()

            if exp_activation_function == "tanhshrink" :

                self.act = torch.nn.Tanhshrink()

            if exp_activation_function == "relu" :

                self.act = torch.nn.ReLU()

            if exp_activation_function == "leakyrelu" :

                self.act = torch.nn.LeakyReLU()
        
        else :

            self.act = torch.nn.Tanhshrink()

    def forward(self, x_in):

        x = self.fc_start_1(x_in)
        x = self.act(x)

        x = self.fc_middle(x)
        x = self.act(x)

        x = self.fc_middle(x)
        x = self.act(x)

        x = self.fc_end(x)

        x = torch.reshape(
            x, shape=(x.shape[0], experiment.N_DIM_THETA*experiment.N_TRAJOPT, 2))

        # theta = arctan(y/x) = arctan(1.0*sin(theta)/1.0*cos(theta))
        theta = torch.atan2(x[:, :, 0], x[:, :, 1])

        #theta = - (math.pi + theta) / 2.0

        #theta = self.fc_end_alt(x)
        #theta = theta % math.pi

        return theta


def save_script(directory):

    # saves a copy of the current python script into the folder
    shutil.copy(__file__, pathlib.Path(directory, os.path.basename(__file__)))


helper.initialize_directories(directories)

# saves a copy of the current python script into folder dir_path_id
save_script(dir_path_id)
helper.save_script(dir_path_id)
experiment.save_script(dir_path_id)

if True and torch.cuda.is_available():

    device = "cuda:0"
    print("CUDA is available! Computing on GPU.")

else:

    device = "cpu"
    print("CUDA is unavailable! Computing on CPU.")

device = torch.device(device)

filemode_logger = "w"

if os.path.exists(pathlib.Path(dir_path_id, helper.log_file_str)):

    filemode_logger = "a"

file_handle_logger = open(pathlib.Path(
    dir_path_id, helper.log_file_str), mode=filemode_logger)

sys_stdout_original = sys.stdout
sys.stdout = helper.Logger(sys_stdout_original, file_handle_logger)

experiment.compute_and_save_joint_angles_region_plot(
    device,
    N_SAMPLES_THETA,
    helper.SAVEFIG_DPI,
    dir_path_id_plots,
    experiment.identifier_string + "_joint_angles_region_plot")

if IS_ONLY_PLOT_REGION:

    exit(0)

model = Model().to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR_INITIAL)
scheduler = torch.optim.lr_scheduler.MultiplicativeLR(
    optimizer, lr_lambda=lambda epoch: LR_SCHEDULER_MULTIPLICATIVE_REDUCTION)

tb_writer = SummaryWriter(
    log_dir=dir_path_id,
    filename_suffix="_" + experiment.identifier_string
)

X_state_train_all = torch.tensor([helper.compute_sample(experiment.LIMITS, experiment.SAMPLE_CIRCLE, experiment.RADIUS_OUTER, experiment.RADIUS_INNER) for _ in range(
    N_SAMPLES_TRAIN)], dtype=helper.DTYPE_TORCH).to(device)
X_state_val = torch.tensor([helper.compute_sample(experiment.LIMITS, experiment.SAMPLE_CIRCLE, experiment.RADIUS_OUTER, experiment.RADIUS_INNER) for _ in range(
    N_SAMPLES_VAL)], dtype=helper.DTYPE_TORCH).to(device)
X_state_test = torch.tensor([helper.compute_sample(experiment.LIMITS, experiment.SAMPLE_CIRCLE, experiment.RADIUS_OUTER, experiment.RADIUS_INNER) for _ in range(
    N_SAMPLES_TEST)], dtype=helper.DTYPE_TORCH).to(device)

X_state_train_all_sorted = torch.zeros_like(X_state_train_all).to(device)

experiment.compute_and_save_samples_plot(X_state_train_all.detach().cpu(), X_state_val.detach(
).cpu(), X_state_test.detach().cpu(), dir_path_id_plots, "samples_plot.jpg")

print("\nTraining Starts!\n")

time_measure = 0
cur_index = 0
diffs = []

X_state_train = 0

distances = 0
distance_index = 0
distances_indices_sorted = 0

for j in range(N_ITERATIONS):

    tic_loop = time.perf_counter()

    cur_index += 1
    current_lr = optimizer.param_groups[0]['lr']

    if SAMPLING_MODE == 0:

        X_state_train = X_state_train_all

    elif SAMPLING_MODE == 1:

        # j == 0 is just a sanity check such that
        # we have a train set for the first iteration

        if j == 0 or j % MODE_1_MODULO_FACTOR == 0:

            X_state_train = torch.tensor([helper.compute_sample(experiment.LIMITS, experiment.SAMPLE_CIRCLE, experiment.RADIUS_OUTER, experiment.RADIUS_INNER) for _ in range(
                N_SAMPLES_TRAIN)], dtype=helper.DTYPE_TORCH).to(device)

    elif SAMPLING_MODE == 2:

        if j == 0:

            index_rng = random.randrange(0, N_SAMPLES_TRAIN)
            X_state_train = X_state_train_all[index_rng:index_rng+1]

            distances = torch.norm(
                (X_state_train_all - X_state_train[0]), p=2, dim=-1)
            distances_indices_sorted = torch.argsort(
                distances, descending=False)
            X_state_train_all_sorted = X_state_train_all[distances_indices_sorted].clone()
            distance_index = 1

        else:

            if distance_index < N_SAMPLES_TRAIN and j % DIVISOR == 0:

                # maximally 10% of the iterations needed until full batch
                offset = int(max(N_SAMPLES_TRAIN // (TENTH / DIVISOR), 1))
                if distance_index + offset > N_SAMPLES_TRAIN:
                    offset = N_SAMPLES_TRAIN - distance_index

                X_new = X_state_train_all_sorted[distance_index:distance_index+offset]

                if IS_MODE_2_ABLATION:

                    X_new = X_state_train_all[distance_index:distance_index+offset]

                X_state_train = torch.cat((X_state_train, X_new), dim=0)

                distance_index += offset

    [loss_train, terminal_position_distance_metrics_train] = helper.compute_loss(
        experiment.compute_energy, model, X_state_train, IS_TWOLINKAGE_CONSTRAINED)

    optimizer.zero_grad()
    loss_train.backward()
    # prevent potential exploding gradients
    #torch.nn.utils.clip_grad_norm_(model.parameters(), 1000.0)
    optimizer.step()
    #scheduler.step()

    if j < 3 * N_ITERATIONS // 4 :

        optimizer.param_groups[0]['lr'] = current_lr * LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_1
    
    else :

        optimizer.param_groups[0]['lr'] = current_lr * LR_SCHEDULER_MULTIPLICATIVE_REDUCTION_2

    toc_loop = time.perf_counter()
    time_measure_tmp = (toc_loop - tic_loop)
    time_measure += time_measure_tmp

    if cur_index % helper.TENSORBOARD_UPDATE == 0 or j == 0:

        print(f"{cur_index} iterations {current_lr} lr {time_measure_tmp:0.2f} [s] (total {time_measure:0.2f} [s])")

        loss_val = 0
        terminal_position_distance_metrics_val = {}
        dloss_train_dW = 0

        with torch.no_grad():

            dloss_train_dW = helper.compute_dloss_dW(model)

            [loss_val, terminal_position_distance_metrics_val] = helper.compute_loss(
                experiment.compute_energy, model, X_state_val, IS_TWOLINKAGE_CONSTRAINED)

            tb_writer.add_scalar('Learning Rate', current_lr, cur_index)
            tb_writer.add_scalar(
                'Train Loss', loss_train.detach().cpu(), cur_index)
            tb_writer.add_scalar(
                'Mean Train Terminal Position Distance [m]', terminal_position_distance_metrics_train['mean'], cur_index)
            tb_writer.add_scalar(
                'Stddev Train Terminal Position Distance [m]', terminal_position_distance_metrics_train['stddev'], cur_index)
            tb_writer.add_scalar(
                'Val Loss', loss_val.detach().cpu(), cur_index)
            tb_writer.add_scalar(
                'Mean Val Terminal Position Distance [m]', terminal_position_distance_metrics_val['mean'], cur_index)
            tb_writer.add_scalar(
                'Stddev Val Terminal Position Distance [m]', terminal_position_distance_metrics_val['stddev'], cur_index)
            tb_writer.add_scalar('Loss Gradient Norm',
                                 dloss_train_dW, cur_index)

        metrics = terminal_position_distance_metrics_val
        txt_dict['iteration'] += '\n' + str(cur_index)
        txt_dict['lr'] += '\n' + str(current_lr)
        txt_dict['mean'] += '\n' + str(metrics['mean'])
        txt_dict['stddev'] += '\n' + str(metrics['stddev'])
        txt_dict['min'] += '\n' + str(metrics['min'])
        txt_dict['max'] += '\n' + str(metrics['max'])
        txt_dict['median'] += '\n' + str(metrics['median'])
        txt_dict['75percentile'] += '\n' + str(metrics['75percentile'])
        txt_dict['90percentile'] += '\n' + str(metrics['90percentile'])
        txt_dict['95percentile'] += '\n' + str(metrics['95percentile'])
        txt_dict['99percentile'] += '\n' + str(metrics['99percentile'])

        print(f"Val / Test Mean: {metrics['mean']:.3e}")

loss_test = 0
terminal_position_distance_metrics_test = {}

with torch.no_grad():

    [loss_test, terminal_position_distance_metrics_test] = helper.compute_loss(
        experiment.compute_energy, model, X_state_test, IS_TWOLINKAGE_CONSTRAINED)

    tb_writer.add_scalar(
        'Test Loss', loss_test.detach().cpu(), cur_index)
    tb_writer.add_scalar(
        'Mean Test Terminal Position Distance [m]', terminal_position_distance_metrics_test['mean'], cur_index)
    tb_writer.add_scalar(
        'Stddev Test Terminal Position Distance [m]', terminal_position_distance_metrics_test['stddev'], cur_index)

X_samples = X_state_test
metrics = terminal_position_distance_metrics_test

n_one_dim = helper.N_ONE_DIM
plot_dpi = helper.SAVEFIG_DPI

constrained_string = helper.convert_constrained_boolean_to_string(
    IS_TWOLINKAGE_CONSTRAINED)
sampling_string = helper.convert_sampling_mode_to_string(
    SAMPLING_MODE)

string_tmp = f'\nIteration {cur_index}, {sampling_string}{constrained_string}\n'

tic = time.perf_counter()

helper.compute_and_save_robot_plot(
    experiment.compute_energy,
    experiment.visualize_trajectory_and_save_image,
    model,
    X_samples,
    IS_TWOLINKAGE_CONSTRAINED,
    "robot_plot",
    dir_path_id_plots
)

toc = time.perf_counter()
print(f"{toc - tic:0.2f} [s] for compute_and_save_robot_plot(...)")

tic = time.perf_counter()

experiment.compute_and_save_joint_angles_plot(
    model,
    device,
    X_state_train,
    plot_dpi,
    n_one_dim,
    dir_path_id_plots,
    experiment.identifier_string + "_" + helper.JOINT_PLOT_NAME,
    helper.plots_fontdict,
    string_tmp + experiment.string_title_joint_angles_plot
)

toc = time.perf_counter()
print(
    f"{toc - tic:0.2f} [s] for compute_and_save_joint_angles_plot(...)")

tic = time.perf_counter()

experiment.compute_and_save_terminal_energy_plot(
    model,
    device,
    X_state_train,
    plot_dpi,
    IS_TWOLINKAGE_CONSTRAINED,
    n_one_dim,
    dir_path_id_plots,
    experiment.identifier_string + "_" + helper.HEATMAP_PLOT_NAME,
    helper.plots_fontdict,
    string_tmp + experiment.string_title_terminal_energy_plot
)

toc = time.perf_counter()
print(
    f"{toc - tic:0.2f} [s] for compute_and_save_terminal_energy_plot(...)")

tic = time.perf_counter()

experiment.compute_and_save_jacobian_plot(
    model,
    device,
    X_state_train,
    plot_dpi,
    n_one_dim,
    dir_path_id_plots,
    experiment.identifier_string + "_" + helper.JACOBIAN_PLOT_NAME,
    helper.plots_fontdict,
    string_tmp + experiment.string_title_jacobian_plot
)

toc = time.perf_counter()
print(
    f"{toc - tic:0.2f} [s] for compute_and_save_jacobian_plot(...)")

tic = time.perf_counter()

helper.compute_and_save_terminal_energy_histogram(
    experiment.compute_energy,
    model,
    X_samples,
    plot_dpi,
    IS_TWOLINKAGE_CONSTRAINED,
    dir_path_id_plots,
    experiment.identifier_string + "_" + helper.HEATMAP_HISTOGRAM_NAME,
    helper.plots_fontdict,
    string_tmp + experiment.string_title_terminal_energy_histogram
)

toc = time.perf_counter()
print(
    f"{toc - tic:0.2f} [s] for compute_and_save_terminal_energy_histogram(...)")

tic = time.perf_counter()

helper.compute_and_save_jacobian_histogram(
    model,
    X_samples,
    plot_dpi,
    dir_path_id_plots,
    experiment.identifier_string + "_" + helper.JACOBIAN_HISTOGRAM_NAME,
    helper.plots_fontdict,
    string_tmp + experiment.string_title_jacobian_histogram
)

toc = time.perf_counter()

print(
    f"{toc - tic:0.2f} [s] for compute_and_save_jacobian_histogram(...)")


print("\nTraining Process Completed.\n")

helper.save_model(model, cur_index, dir_path_id_model,
                  helper.nn_model_state_dict_only_str, helper.nn_model_full_str)

helper.compute_and_save_metrics_txt(txt_dict, metrics, N_ITERATIONS, dir_path_id,
                                    "terminal_position_distance_metrics.txt")

print("\nAll Done!\n")

sys.stdout = sys_stdout_original
file_handle_logger.close()
