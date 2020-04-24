# -*- coding: utf-8 -*-

# Copyright 2020 Minh Nguyen (@dathudeptrai)
#  MIT License (https://opensource.org/licenses/MIT)

"""Dataset modules."""

import logging
import os

from multiprocessing import Manager

import tensorflow as tf

from tensorflow_tts.utils import find_files
from tensorflow_tts.utils import read_hdf5

from tensorflow_tts.datasets.abstract_dataset import AbstractDataset


class AudioMelDataset(AbstractDataset):
    """Tensorflow Audio Mel dataset."""

    def __init__(self,
                 root_dir,
                 audio_query="*.h5",
                 mel_query="*.h5",
                 audio_load_fn=lambda x: read_hdf5(x, "wave"),
                 mel_load_fn=lambda x: read_hdf5(x, "feats"),
                 audio_length_threshold=None,
                 mel_length_threshold=None,
                 return_utt_id=False
                 ):
        """Initialize dataset.

        Args:
            root_dir (str): Root directory including dumped files.
            audio_query (str): Query to find audio files in root_dir.
            mel_query (str): Query to find feature files in root_dir.
            audio_load_fn (func): Function to load audio file.
            mel_load_fn (func): Function to load feature file.
            audio_length_threshold (int): Threshold to remove short audio files.
            mel_length_threshold (int): Threshold to remove short feature files.
            return_utt_id (bool): Whether to return the utterance id with arrays.

        """
        # find all of audio and mel files.
        audio_files = sorted(find_files(root_dir, audio_query))
        mel_files = sorted(find_files(root_dir, mel_query))

        # filter by threshold
        if audio_length_threshold is not None:
            audio_lengths = [audio_load_fn(f).shape[0] for f in audio_files]
            idxs = [idx for idx in range(len(audio_files)) if audio_lengths[idx] > audio_length_threshold]
            if len(audio_files) != len(idxs):
                logging.warning(f"Some files are filtered by audio length threshold "
                                f"({len(audio_files)} -> {len(idxs)}).")
            audio_files = [audio_files[idx] for idx in idxs]
            mel_files = [mel_files[idx] for idx in idxs]
        if mel_length_threshold is not None:
            mel_lengths = [mel_load_fn(f).shape[0] for f in mel_files]
            idxs = [idx for idx in range(len(mel_files)) if mel_lengths[idx] > mel_length_threshold]
            if len(mel_files) != len(idxs):
                logging.warning(f"Some files are filtered by mel length threshold "
                                f"({len(mel_files)} -> {len(idxs)}).")
            audio_files = [audio_files[idx] for idx in idxs]
            mel_files = [mel_files[idx] for idx in idxs]

        # assert the number of files
        assert len(audio_files) != 0, f"Not found any audio files in ${root_dir}."
        assert len(audio_files) == len(mel_files), \
            f"Number of audio and mel files are different ({len(audio_files)} vs {len(mel_files)})."

        if ".npy" in audio_query:
            utt_ids = [os.path.basename(f).replace("-wave.npy", "") for f in audio_files]
        else:
            utt_ids = [os.path.splitext(os.path.basename(f))[0] for f in audio_files]

        # set global params
        self.utt_ids = utt_ids
        self.audio_files = audio_files
        self.mel_files = mel_files
        self.audio_load_fn = audio_load_fn
        self.mel_load_fn = mel_load_fn
        self.return_utt_id = return_utt_id

    def get_args(self):
        return [self.utt_ids]

    def generator(self, utt_ids):
        for i, utt_id in enumerate(utt_ids):
            audio_file = self.audio_files[i]
            mel_file = self.mel_files[i]
            audio = self.audio_load_fn(audio_file)  # [T]
            mel = self.mel_load_fn(mel_file)
            if self.return_utt_id:
                items = utt_id, audio, mel
            else:
                items = audio, mel
            yield items

    def get_output_dtypes(self):
        output_types = (tf.float32, tf.float32)
        if self.return_utt_id:
            output_types = (tf.dtypes.string, *output_types)
        return output_types

    def get_len_dataset(self):
        return len(self.utt_ids)

    def __name__(self):
        return "AudioMelDataset"


class AudioDataset(AbstractDataset):
    """Tensorflow compatible audio dataset."""

    def __init__(self,
                 root_dir,
                 audio_query="*.h5",
                 audio_load_fn=lambda x: read_hdf5(x, "wave"),
                 audio_length_threshold=None,
                 return_utt_id=False,
                 ):
        """Initialize dataset.

        Args:
            root_dir (str): Root directory including dumped files.
            audio_query (str): Query to find audio files in root_dir.
            audio_load_fn (func): Function to load audio file.
            audio_length_threshold (int): Threshold to remove short audio files.
            return_utt_id (bool): Whether to return the utterance id with arrays.

        """
        # find all of audio files.
        audio_files = sorted(find_files(root_dir, audio_query))

        # filter by threshold
        if audio_length_threshold is not None:
            audio_lengths = [audio_load_fn(f).shape[0] for f in audio_files]
            idxs = [idx for idx in range(len(audio_files)) if audio_lengths[idx] > audio_length_threshold]
            if len(audio_files) != len(idxs):
                logging.warning(f"Some files are filtered by audio length threshold "
                                f"({len(audio_files)} -> {len(idxs)}).")
            audio_files = [audio_files[idx] for idx in idxs]

        # assert the number of files
        assert len(audio_files) != 0, f"Not found any audio files in ${root_dir}."

        if ".npy" in audio_query:
            utt_ids = [os.path.basename(f).replace("-wave.npy", "") for f in audio_files]
        else:
            utt_ids = [os.path.splitext(os.path.basename(f))[0] for f in audio_files]

        # set global params
        self.utt_ids = utt_ids
        self.audio_files = audio_files
        self.audio_load_fn = audio_load_fn
        self.return_utt_id = return_utt_id

    def get_args(self):
        return [self.utt_ids]

    def generator(self, utt_ids):
        for i, utt_id in enumerate(utt_ids):
            audio_file = self.audio_files[i]
            audio = self.audio_load_fn(audio_file)  # [T]
            if self.return_utt_id:
                items = utt_id, audio
            else:
                items = audio
            yield items

    def get_output_dtypes(self):
        output_types = (tf.float32)
        if self.return_utt_id:
            output_types = (tf.dtypes.string, *output_types)
        return output_types

    def __name__(self):
        return "AudioDataset"


class MelDataset(AbstractDataset):
    """Tensorflow compatible mel dataset."""

    def __init__(self,
                 root_dir,
                 mel_query="*.h5",
                 mel_load_fn=lambda x: read_hdf5(x, "feats"),
                 mel_length_threshold=None,
                 return_utt_id=False
                 ):
        """Initialize dataset.

        Args:
            root_dir (str): Root directory including dumped files.
            mel_query (str): Query to find feature files in root_dir.
            mel_load_fn (func): Function to load feature file.
            mel_length_threshold (int): Threshold to remove short feature files.
            return_utt_id (bool): Whether to return the utterance id with arrays.

        """
        # find all of mel files.
        mel_files = sorted(find_files(root_dir, mel_query))

        # filter by threshold
        if mel_length_threshold is not None:
            mel_lengths = [mel_load_fn(f).shape[0] for f in mel_files]
            idxs = [idx for idx in range(len(mel_files)) if mel_lengths[idx] > mel_length_threshold]
            if len(mel_files) != len(idxs):
                logging.warning(f"Some files are filtered by mel length threshold "
                                f"({len(mel_files)} -> {len(idxs)}).")
            mel_files = [mel_files[idx] for idx in idxs]

        # assert the number of files
        assert len(mel_files) != 0, f"Not found any mel files in ${root_dir}."

        if ".npy" in mel_query:
            utt_ids = [os.path.basename(f).replace("-feats.npy", "") for f in mel_files]
        else:
            utt_ids = [os.path.splitext(os.path.basename(f))[0] for f in mel_files]

        # set global params
        self.utt_ids = utt_ids
        self.mel_files = mel_files
        self.mel_load_fn = mel_load_fn
        self.return_utt_id = return_utt_id

    def get_args(self):
        return [self.utt_ids]

    def generator(self, utt_ids):
        for i, utt_id in enumerate(utt_ids):
            mel_file = self.mel_files[i]
            mel = self.mel_load_fn(mel_file)
            if self.return_utt_id:
                items = utt_id, mel
            else:
                items = mel
            yield items

    def get_output_dtypes(self):
        output_types = (tf.float32)
        if self.return_utt_id:
            output_types = (tf.dtypes.string, *output_types)
        return output_types

    def __name__(self):
        return "MelDataset"
