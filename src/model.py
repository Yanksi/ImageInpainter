import tensorflow as tf
from model_building_blocks import *
from losses import *
import os

class InpaitingModel:
    def __init__(self, model_config):
        self.config = model_config
        self.edge_generator = EdgeGenerator(config=model_config["edge"]["generator"], name="EdgeGenerator")
        self.eg_opt = tf.keras.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)

        self.inpainting_generator = InpaitingGenerator(config=model_config["clr"]["generator"], name="InpaitingGenerator")
        self.ig_opt = tf.keras.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)

        self.edge_discriminator = EdgeDiscriminator(name="EdgeDiscriminator")
        self.ed_opt = tf.keras.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)

        self.inpainting_discriminator = InpaintingDiscriminator(name="InpaintingDiscriminator")
        self.id_opt = tf.keras.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)

        self.perceptual_and_style_loss = PerceptuaAndStylelLoss(name="PL_Loss")

        try:
            if model_config['use_pretrained_weights']:
                self.edge_generator.load_weights(os.path.join(model_config['model_ckpoint_dir'], "eg_weights"))
                self.edge_discriminator.load_weights(os.path.join(model_config['model_ckpoint_dir'], "ed_weights"))
                self.inpainting_generator.load_weights(os.path.join(model_config['model_ckpoint_dir'], "ig_weights"))
                self.inpainting_discriminator.load_weights(os.path.join(model_config['model_ckpoint_dir'], "id_weights"))
                print("pretrained weights loaded")
            else:
                for f in os.listdir(model_config['model_ckpoint_dir']):
                    os.remove(os.path.join(model_config['model_ckpoint_dir'], f))
                print("ignored pretrained results")
        except:
            print("no available weights")
    
    def check_pointing_edge_models(self):
        self.edge_generator.save_weights(os.path.join(self.config['model_ckpoint_dir'], "eg_weights"))
        self.edge_discriminator.save_weights(os.path.join(self.config['model_ckpoint_dir'], "ed_weights"))
    
    def check_pointing_inpainting_models(self):
        self.inpainting_generator.save_weights(os.path.join(self.config['model_ckpoint_dir'], "ig_weights"))
        self.inpainting_discriminator.save_weights(os.path.join(self.config['model_ckpoint_dir'], "id_weights"))
    
    @tf.function
    def edge_train_step(self, masked_gray_img, edge, mask):
        masked_edge = mask * edge
        with tf.GradientTape(persistent=True) as tape:
            fake_edge = self.edge_generator(masked_gray_img, masked_edge, mask)
            adv_loss, lfm = self.edge_discriminator.generator_loss(fake_edge, edge)
            gen_loss = self.config["edge"]["lamb_adv"] * adv_loss + self.config["edge"]["lamb_fm"] * lfm
            disc_loss = self.edge_discriminator.discriminator_loss(fake_edge, edge)
        
        gen_grad = tape.gradient(gen_loss, self.edge_generator.trainable_variables)
        disc_grad = tape.gradient(disc_loss, self.edge_discriminator.trainable_variables)

        self.eg_opt.apply_gradients(zip(gen_grad, self.edge_generator.trainable_variables))
        self.ed_opt.apply_gradients(zip(disc_grad, self.edge_discriminator.trainable_variables))
 
    @tf.function
    def inpainting_train_step(self, edge, clr_img, mask):
        masked_clr = mask * clr_img
        with tf.GradientTape(persistent=True) as tape:
            fake_clr = self.inpainting_generator(edge, masked_clr, mask)
            adv_loss = self.inpainting_discriminator.generator_loss(fake_clr, clr_img)
            perc_loss, style_loss = self.perceptual_and_style_loss(fake_clr, clr_img)
            l1_loss = reconstruction_loss(fake_clr, clr_img)
            gen_loss = self.config["clr"]["lamb_l1"] * l1_loss +\
                    self.config["clr"]["lamb_adv"] * adv_loss +\
                    self.config["clr"]["lamb_perc"] * perc_loss +\
                    self.config["clr"]["lamb_style"] * style_loss
            disc_loss = self.inpainting_discriminator.discriminator_loss(fake_clr, clr_img)
        
        gen_grad = tape.gradient(gen_loss, self.inpainting_generator.trainable_variables)
        disc_grad = tape.gradient(disc_loss, self.inpainting_discriminator.trainable_variables)

        self.ig_opt.apply_gradients(zip(gen_grad, self.inpainting_generator.trainable_variables))
        self.id_opt.apply_gradients(zip(disc_grad, self.inpainting_discriminator.trainable_variables))
    
    @tf.function
    def infer_edge(self, clr_img, edge, mask):
        grey_img = tf.image.rgb_to_grayscale(clr_img)
        masked_grey = grey_img * mask
        masked_edge = edge * mask
        return self.edge_generator(masked_grey, masked_edge, mask)
    
    @tf.function
    def infer_inpainting(self, clr_img, edge, mask):
        masked_clr = clr_img * mask
        return self.inpainting_generator(edge, masked_clr, mask)
    
    @tf.function
    def fused_infer(self, clr_img, edge, mask):
        new_edge = self.infer_edge(clr_img, edge, mask)
        return self.infer_inpainting(clr_img, new_edge, mask)
    
    def train_edge_part(self, edge_dataset, epochs=100):
        for _ in range(epochs):
            for masked_gray, edge, mask in edge_dataset:
                self.edge_train_step(masked_gray, edge, mask)
            self.check_pointing_edge_models()
    
    def train_inpainting_part(self, clr_dataset, epochs=100):
        for _ in range(epochs):
            for edge, clr_img, mask in clr_dataset:
                self.inpainting_train_step(edge, clr_img, mask)
            self.check_pointing_inpainting_models()