#!/bin/python3

import pathlib

benchmark_path = pathlib.Path(pathlib.Path(__file__).parent.resolve(), "benchmark.py")

# Experiment: The RNG Matters

local_globals_list = [
    {
        "exp_SAMPLING_MODE": 0,
    },
    {
        "exp_SAMPLING_MODE": 1,
    },
    {
        "exp_SAMPLING_MODE": 2,
    }
]

for local_globals in local_globals_list :
    with open(benchmark_path) as f:
        code = compile(f.read(), benchmark_path, "exec")
        globals().update(local_globals)
        globals()["__file__"] = benchmark_path
        globals()["exp_N_SAMPLES_TRAIN"] = 1000
        globals()["exp_N_ITERATIONS"] = 10000
        globals()["exp_IS_MODE_2_ABLATION"] = False
        globals()["exp_IS_TWOLINKAGE_CONSTRAINED"] = False
        exec(code, globals())

'''

# Experiment: The Activation Function Matters Too

local_globals_list = [
    {
        "exp_activation_function": "cos"
    },
    {
        "exp_activation_function": "sin"
    },
    {
        "exp_activation_function": "mish"
    },
    {
        "exp_activation_function": "sigmoid"
    },
    {
        "exp_activation_function": "tanh"
    },
    {
        "exp_activation_function": "tanhshrink"
    },
    {
        "exp_activation_function": "relu"
    },
    {
        "exp_activation_function": "leakyrelu"
    }
]

for local_globals in local_globals_list :
    with open(benchmark_path) as f:
        code = compile(f.read(), benchmark_path, "exec")
        globals().update(local_globals)
        globals()["__file__"] = benchmark_path
        globals()["exp_SAMPLING_MODE"] = 0
        globals()["exp_IS_TWOLINKAGE_CONSTRAINED"] = False
        globals()["exp_IS_MODE_2_ABLATION"] = False
        globals()["exp_N_SAMPLES_TRAIN"] = 1000
        globals()["exp_N_ITERATIONS"] = 10000
        exec(code, globals())

'''