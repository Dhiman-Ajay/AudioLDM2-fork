import contextlib
import importlib
from huggingface_hub import hf_hub_download

from inspect import isfunction
import os
import soundfile as sf
import time
import wave

import progressbar

CACHE_DIR = os.getenv(
    "AUDIOLDM_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".cache/audioldm2")
)

def read_list(fname):
    result = []
    with open(fname, "r", encoding="utf-8") as f:
        for each in f.readlines():
            each = each.strip('\n')
            result.append(each)
    return result

def get_duration(fname):
    with contextlib.closing(wave.open(fname, "r")) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)


def get_bit_depth(fname):
    with contextlib.closing(wave.open(fname, "r")) as f:
        bit_depth = f.getsampwidth() * 8
        return bit_depth


def get_time():
    t = time.localtime()
    return time.strftime("%d_%m_%Y_%H_%M_%S", t)


def seed_everything(seed):
    import random, os
    import numpy as np
    import torch

    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True


def save_wave(waveform, savepath, name="outwav"):
    if type(name) is not list:
        name = [name] * waveform.shape[0]

    for i in range(waveform.shape[0]):
        path = os.path.join(
            savepath,
            "%s_%s.wav"
            % (
                os.path.basename(name[i])
                if (not ".wav" in name[i])
                else os.path.basename(name[i]).split(".")[0],
                i,
            ),
        )
        print("Save audio to %s" % path)
        sf.write(path, waveform[i, 0], samplerate=16000)


def exists(x):
    return x is not None


def default(val, d):
    if exists(val):
        return val
    return d() if isfunction(d) else d


def count_params(model, verbose=False):
    total_params = sum(p.numel() for p in model.parameters())
    if verbose:
        print(f"{model.__class__.__name__} has {total_params * 1.e-6:.2f} M params.")
    return total_params


def get_obj_from_str(string, reload=False):
    module, cls = string.rsplit(".", 1)
    if reload:
        module_imp = importlib.import_module(module)
        importlib.reload(module_imp)
    return getattr(importlib.import_module(module, package=None), cls)


def instantiate_from_config(config):
    if not "target" in config:
        if config == "__is_first_stage__":
            return None
        elif config == "__is_unconditional__":
            return None
        raise KeyError("Expected key `target` to instantiate.")
    try:
        return get_obj_from_str(config["target"])(**config.get("params", dict()))
    except:
        import ipdb

        ipdb.set_trace()


def default_audioldm_config(model_name="audioldm2-full"):
    basic_config = {
        "metadata_root": "/mnt/bn/lqhaoheliu/metadata/processed/dataset_root.json",
        "log_directory": "./log/audiomae_pred",
        "precision": "high",
        "data": {
            "train": [
                "audiocaps",
                "audioset",
                "wavcaps",
                "audiostock_music_250k",
                "free_to_use_sounds",
                "epidemic_sound_effects",
                "vggsound",
                "million_song_dataset",
            ],
            "val": "audiocaps",
            "test": "audiocaps",
            "class_label_indices": "audioset",
            "dataloader_add_ons": [
                "extract_kaldi_fbank_feature",
                "extract_vits_phoneme_and_flant5_text",
                "waveform_rs_48k",
            ],
        },
        "variables": {
            "sampling_rate": 16000,
            "mel_bins": 64,
            "latent_embed_dim": 8,
            "latent_t_size": 256,
            "latent_f_size": 16,
            "in_channels": 8,
            "optimize_ddpm_parameter": True,
            "warmup_steps": 5000,
        },
        "step": {
            "validation_every_n_epochs": 1,
            "save_checkpoint_every_n_steps": 5000,
            "limit_val_batches": 10,
            "max_steps": 1500000,
            "save_top_k": 2,
        },
        "preprocessing": {
            "audio": {
                "sampling_rate": 16000,
                "max_wav_value": 32768,
                "duration": 10.24,
            },
            "stft": {"filter_length": 1024, "hop_length": 160, "win_length": 1024},
            "mel": {"n_mel_channels": 64, "mel_fmin": 0, "mel_fmax": 8000},
        },
        "augmentation": {"mixup": 0},
        "model": {
            "target": "audioldm2.latent_diffusion.models.ddpm.LatentDiffusion",
            "params": {
                "first_stage_config": {
                    "base_learning_rate": 0.000008,
                    "target": "audioldm2.latent_encoder.autoencoder.AutoencoderKL",
                    "params": {
                        "sampling_rate": 16000,
                        "batchsize": 4,
                        "monitor": "val/rec_loss",
                        "image_key": "fbank",
                        "subband": 1,
                        "embed_dim": 8,
                        "time_shuffle": 1,
                        "lossconfig": {
                            "target": "audioldm2.latent_diffusion.modules.losses.LPIPSWithDiscriminator",
                            "params": {
                                "disc_start": 50001,
                                "kl_weight": 1000,
                                "disc_weight": 0.5,
                                "disc_in_channels": 1,
                            },
                        },
                        "ddconfig": {
                            "double_z": True,
                            "mel_bins": 64,
                            "z_channels": 8,
                            "resolution": 256,
                            "downsample_time": False,
                            "in_channels": 1,
                            "out_ch": 1,
                            "ch": 128,
                            "ch_mult": [1, 2, 4],
                            "num_res_blocks": 2,
                            "attn_resolutions": [],
                            "dropout": 0,
                        },
                    },
                },
                "base_learning_rate": 0.0001,
                "warmup_steps": 5000,
                "optimize_ddpm_parameter": True,
                "sampling_rate": 16000,
                "batchsize": 16,
                "linear_start": 0.0015,
                "linear_end": 0.0195,
                "num_timesteps_cond": 1,
                "log_every_t": 200,
                "timesteps": 1000,
                "unconditional_prob_cfg": 0.1,
                "parameterization": "eps",
                "first_stage_key": "fbank",
                "latent_t_size": 256,
                "latent_f_size": 16,
                "channels": 8,
                "monitor": "val/loss_simple_ema",
                "scale_by_std": True,
                "unet_config": {
                    "target": "audioldm2.latent_diffusion.modules.diffusionmodules.openaimodel.UNetModel",
                    "params": {
                        "image_size": 64,
                        "context_dim": [768, 1024],
                        "in_channels": 8,
                        "out_channels": 8,
                        "model_channels": 128,
                        "attention_resolutions": [8, 4, 2],
                        "num_res_blocks": 2,
                        "channel_mult": [1, 2, 3, 5],
                        "num_head_channels": 32,
                        "use_spatial_transformer": True,
                        "transformer_depth": 1,
                    },
                },
                "evaluation_params": {
                    "unconditional_guidance_scale": 3.5,
                    "ddim_sampling_steps": 200,
                    "n_candidates_per_samples": 3,
                },
                "cond_stage_config": {
                    "crossattn_audiomae_generated": {
                        "cond_stage_key": "all",
                        "conditioning_key": "crossattn",
                        "target": "audioldm2.latent_diffusion.modules.encoders.modules.SequenceGenAudioMAECond",
                        "params": {
                            "always_output_audiomae_gt": False,
                            "learnable": True,
                            "device": "cuda",
                            "use_gt_mae_output": True,
                            "use_gt_mae_prob": 0.25,
                            "base_learning_rate": 0.0002,
                            "sequence_gen_length": 8,
                            "use_warmup": True,
                            "sequence_input_key": [
                                "film_clap_cond1",
                                "crossattn_flan_t5",
                            ],
                            "sequence_input_embed_dim": [512, 1024],
                            "batchsize": 16,
                            "cond_stage_config": {
                                "film_clap_cond1": {
                                    "cond_stage_key": "text",
                                    "conditioning_key": "film",
                                    "target": "audioldm2.latent_diffusion.modules.encoders.modules.CLAPAudioEmbeddingClassifierFreev2",
                                    "params": {
                                        "sampling_rate": 48000,
                                        "embed_mode": "text",
                                        "amodel": "HTSAT-base",
                                    },
                                },
                                "crossattn_flan_t5": {
                                    "cond_stage_key": "text",
                                    "conditioning_key": "crossattn",
                                    "target": "audioldm2.latent_diffusion.modules.encoders.modules.FlanT5HiddenState",
                                },
                                "crossattn_audiomae_pooled": {
                                    "cond_stage_key": "ta_kaldi_fbank",
                                    "conditioning_key": "crossattn",
                                    "target": "audioldm2.latent_diffusion.modules.encoders.modules.AudioMAEConditionCTPoolRand",
                                    "params": {
                                        "regularization": False,
                                        "no_audiomae_mask": True,
                                        "time_pooling_factors": [8],
                                        "freq_pooling_factors": [8],
                                        "eval_time_pooling": 8,
                                        "eval_freq_pooling": 8,
                                        "mask_ratio": 0,
                                    },
                                },
                            },
                        },
                    },
                    "crossattn_flan_t5": {
                        "cond_stage_key": "text",
                        "conditioning_key": "crossattn",
                        "target": "audioldm2.latent_diffusion.modules.encoders.modules.FlanT5HiddenState",
                    },
                },
            },
        },
    }
    return basic_config


def get_metadata():
    return {
        "audioldm2-full": {
            "path": os.path.join(
                CACHE_DIR,
                "audioldm2-full.pth",
            ),
            "url": "https://huggingface.co/haoheliu/audioldm2-full/resolve/main/audioldm2-full.pth",
        },
    }


class MyProgressBar:
    def __init__(self):
        self.pbar = None

    def __call__(self, block_num, block_size, total_size):
        if not self.pbar:
            self.pbar = progressbar.ProgressBar(maxval=total_size)
            self.pbar.start()

        downloaded = block_num * block_size
        if downloaded < total_size:
            self.pbar.update(downloaded)
        else:
            self.pbar.finish()


def download_checkpoint(checkpoint_name="audioldm2-full"):
    meta = get_metadata()
    if checkpoint_name not in meta.keys():
        print(
            "The model name you provided is not supported. Please use one of the following: ",
            meta.keys(),
        )

    model_id = "haoheliu/%s" % checkpoint_name
    hf_hub_download(
        repo_id=model_id,
        filename=os.path.basename(meta[checkpoint_name]["path"]),
        local_dir=os.path.dirname(meta[checkpoint_name]["path"]),
    )