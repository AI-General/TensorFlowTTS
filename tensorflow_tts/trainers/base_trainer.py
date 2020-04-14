# -*- coding: utf-8 -*-

# Copyright 2020 Minh Nguyen Quan Anh
#  MIT License (https://opensource.org/licenses/MIT)

"""Based Trainer."""

import abc
import logging
import os
from tqdm import tqdm

import tensorflow as tf


class GanBasedTrainer(metaclass=abc.ABCMeta):
    """Customized trainer module for MelGAN training."""

    def __init__(self,
                 steps,
                 epochs,
                 config,
                 is_generator_mixed_precision=False,
                 is_discriminator_mixed_precision=False,
                 ):
        """Initialize trainer.

        Args:
            steps (int): Initial global steps.
            epochs (int): Initial global epochs.
            config (dict): Config dict loaded from yaml format configuration file.

        """
        self.steps = steps
        self.epochs = epochs
        self.config = config
        self.writer = tf.summary.create_file_writer(config["outdir"])
        self.finish_train = False
        self.is_generator_mixed_precision = is_generator_mixed_precision
        self.is_discriminator_mixed_precision = is_discriminator_mixed_precision

    def set_train_data_loader(self, train_dataset):
        """Set train data loader (MUST)."""
        self.train_data_loader = train_dataset

    def get_train_data_loader(self):
        """Get train data loader."""
        return self.train_data_loader

    def set_eval_data_loader(self, eval_dataset):
        """Set eval data loader (MUST)."""
        self.eval_data_loader = eval_dataset

    def get_eval_data_loader(self):
        """Get eval data loader."""
        return self.eval_data_loader

    def set_gen_model(self, generator_model):
        """Set generator class model (MUST)."""
        self.generator = generator_model

    def get_gen_model(self):
        """Get generator model."""
        return self.generator

    def set_dis_model(self, discriminator_model):
        """Set discriminator class model (MUST)."""
        self.discriminator = discriminator_model

    def get_dis_model(self):
        """Get discriminator model."""
        return self.discriminator

    def set_gen_optimizer(self, generator_optimizer):
        """Set generator optimizer (MUST)."""
        self.gen_optimizer = generator_optimizer
        if self.is_generator_mixed_precision:
            self.gen_optimizer = tf.keras.mixed_precision.experimental.LossScaleOptimizer(
                self.gen_optimizer, 'dynamic')

    def get_gen_optimizer(self):
        """Get generator optimizer."""
        return self.gen_optimizer

    def set_dis_optimizer(self, discriminator_optimizer):
        """Set discriminator optimizer (MUST)."""
        self.dis_optimizer = discriminator_optimizer
        if self.is_discriminator_mixed_precision:
            self.dis_optimizer = tf.keras.mixed_precision.experimental.LossScaleOptimizer(
                self.dis_optimizer, 'dynamic')

    def get_dis_optimizer(self):
        """Get discriminator optimizer."""
        return self.dis_optimizer

    def create_checkpoint_manager(self,
                                  saved_path=None,
                                  max_to_keep=10):
        """Create checkpoint management."""
        if saved_path is None:
            saved_path = self.config["outdir"] + '/checkpoints/'
            os.makedirs(saved_path, exist_ok=True)

        self.ckpt = tf.train.Checkpoint(steps=tf.Variable(1),
                                        epochs=tf.Variable(1),
                                        generator=self.get_gen_model(),
                                        discriminator=self.get_dis_model(),
                                        gen_optimizer=self.get_gen_optimizer(),
                                        dis_optimizer=self.get_dis_optimizer())
        self.ckp_manager = tf.train.CheckpointManager(self.ckpt,
                                                      saved_path,
                                                      max_to_keep=max_to_keep)

    def run(self):
        """Run training."""
        self.tqdm = tqdm(initial=self.steps,
                         total=self.config["train_max_steps"],
                         desc="[train]")
        while True:
            self._train_epoch()

            if self.finish_train:
                break

        self.tqdm.close()
        logging.info("Finish training.")

    def save_checkpoint(self):
        """Save checkpoint."""
        self.ckpt.steps.assign(self.steps)
        self.ckpt.epochs.assign(self.epochs)
        self.ckp_manager.save(checkpoint_number=self.steps)

    def load_checkpoint(self, pretrained_path):
        """Load checkpoint."""
        self.ckpt.restore(pretrained_path)
        self.steps = self.ckpt.steps.numpy()
        self.epochs = self.ckpt.epochs.numpy()
        self.generator = self.ckpt.generator
        self.discriminator = self.ckpt.discriminator
        self.gen_optimizer = self.ckpt.gen_optimizer
        self.dis_optimizer = self.ckpt.dis_optimizer

    def _train_epoch(self):
        """Train model one epoch."""
        for train_steps_per_epoch, batch in enumerate(self.train_data_loader, 1):
            # one step training
            self._train_step(batch)

            # update counts
            self.steps += 1
            self.tqdm.update(1)
            self._check_train_finish()

            # check interval
            if self.config["rank"] == 0:
                self._check_log_interval()
                self._check_eval_interval()
                self._check_save_interval()

            # check wheter training is finished
            if self.finish_train:
                return

        # update
        self.epochs += 1
        self.train_steps_per_epoch = train_steps_per_epoch
        logging.info(f"(Steps: {self.steps}) Finished {self.epochs} epoch training "
                     f"({self.train_steps_per_epoch} steps per epoch).")

    @abc.abstractmethod
    def _eval_epoch(self):
        """One epoch evaluation."""
        pass

    @abc.abstractmethod
    def _train_step(self, batch):
        """One step training."""
        pass

    @abc.abstractmethod
    def _eval_step(self, batch):
        """One eval step."""
        pass

    @abc.abstractmethod
    def _check_log_interval(self):
        """Save log interval."""
        pass

    def _check_eval_interval(self):
        """Evaluation interval step."""
        if self.steps % self.config["eval_interval_steps"] == 0:
            self._eval_epoch()

    def _check_save_interval(self):
        """Save interval checkpoint."""
        if self.steps % self.config["save_interval_steps"] == 0:
            self.save_checkpoint()
            logging.info(f"Successfully saved checkpoint @ {self.steps} steps.")

    def generate_and_save_intermediate_result(self, batch):
        """Generate and save intermediate result."""
        pass

    def _write_to_tensorboard(self, list_metrics, stage="train"):
        """Write variables to tensorboard."""
        with self.writer.as_default():
            for key, value in list_metrics.items():
                tf.summary.scalar(stage + "/" + key, value.result(), step=self.steps)
                self.writer.flush()

    @abc.abstractmethod
    def _check_train_finish(self):
        """Check training finished."""
        pass