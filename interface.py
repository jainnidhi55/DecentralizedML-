# -*- coding: utf-8 -*-
"""interface.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1m3AsFRknW0punAzrQfpVwqlmy_E1ftEn
"""

# cindy
class client:

  def train(): #train local round
    pass
  
  def recieve_training_info(): #receive info from server: data, training hyperparameters, etc.
    pass
  
  def send_message(): #send message to server
    #execute the random delay
    pass

class server: #NIDHI

  def replica_state(): #state to keep track of replicas for each client 
    pass

  def aggregate(): #aggregate local training rounds (Averaging)
    pass

  def send_message():
    pass

class message:

  # fields 
  # random delay
  #Neha
  pass

class run_training:
  #Neha
  def forward():
    pass
