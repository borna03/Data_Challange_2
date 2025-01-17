import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.functional import interpolate
from typing import Tuple
import matplotlib.pyplot as plt
import numpy as np

class SEBlock(nn.Module):
    def __init__(self, channel, reduction=16):
        super(SEBlock, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channel, channel // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channel // reduction, channel, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c, _, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y.expand_as(x)

class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=2, expansion=1, apply_dropout: bool = False):
        super(ResidualBlock, self).__init__()
        mid_channels = out_channels // expansion
        self.conv1 = nn.Conv2d(in_channels, mid_channels, kernel_size=3, stride=stride, padding=1)
        self.bn1 = nn.BatchNorm2d(mid_channels)
        self.relu = nn.ReLU(inplace=True)

        self.conv2 = nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channels)

        self.downsample = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.downsample = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride),
                nn.BatchNorm2d(out_channels)
            )

        self.apply_dropout = apply_dropout

        #ADD+
        self.se = SEBlock(out_channels)


        if apply_dropout:
            self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        identity = self.downsample(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.dropout(out)

        if self.apply_dropout:
            out = self.dropout(out)  # Apply dropout after the first activation

        out = self.conv2(out)
        out = self.bn2(out)

        #ADD+
        out = self.se(out)

        out += identity
        out = self.relu(out)

        return out

class Net(nn.Module):
    def __init__(self, n_classes: int, depth: int = 3, MCd: bool = False):
        super(Net, self).__init__()
        self.MCd = MCd

        self.init_conv = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
        )

        layers = []

        in_channels = 64

        for i in range(depth):
            out_channels = in_channels * 2 if i else in_channels
            layers.append(ResidualBlock(in_channels, out_channels, stride=2 if i else 1, apply_dropout = True),)
            layers.append(ResidualBlock(out_channels, out_channels, apply_dropout = True))  # Keep the same number of channels within a layer
            in_channels = out_channels

        self.res_layers = nn.Sequential(*layers)

        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))

        # Assuming the output of the last ResidualBlock is `out_channels`, adjust linear layer accordingly.
        self.linear_layers = nn.Sequential(
            nn.Linear(out_channels, n_classes),
        )

    def forward(self, x):
        x = self.init_conv(x)

        x = self.res_layers(x)
        x = self.avg_pool(x)
        x = F.dropout(x, p=0.1)
        x = x.view(x.size(0), -1)
        x = F.dropout(x, p=0.1)

        if self.MCd:
            x = F.dropout(x, p=0.5)

        x = self.linear_layers(x)

        if self.MCd:
            x = F.softmax(x, dim=1)  # Apply softmax to the output of the linear layer

        return x

#SPRINT 2 Model + Baseline

# class ResidualBlock(nn.Module):
#     def __init__(self, in_channels, out_channels, stride=1, expansion=1, apply_dropout: bool = False):
#         super(ResidualBlock, self).__init__()
#         mid_channels = out_channels // expansion
#         self.conv1 = nn.Conv2d(in_channels, mid_channels, kernel_size=3, stride=stride, padding=1)
#         self.bn1 = nn.BatchNorm2d(mid_channels)
#         self.relu = nn.ReLU(inplace=True)
#
#         self.conv2 = nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1)
#         self.bn2 = nn.BatchNorm2d(out_channels)
#
#         self.downsample = nn.Sequential()
#         if stride != 1 or in_channels != out_channels:
#             self.downsample = nn.Sequential(
#                 nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride),
#                 nn.BatchNorm2d(out_channels)
#             )
#
#         self.apply_dropout = apply_dropout
#         if apply_dropout:
#             self.dropout = nn.Dropout(0.5)
#
#     def forward(self, x):
#         identity = self.downsample(x)
#
#         out = self.conv1(x)
#         out = self.bn1(out)
#         out = self.relu(out)
#
#         if self.apply_dropout:
#             out = self.dropout(out)  # Apply dropout after the first activation
#
#         out = self.conv2(out)
#         out = self.bn2(out)
#
#         out += identity
#         out = self.relu(out)
#
#         return out
#
#
# class Net(nn.Module):
#     def __init__(self, n_classes: int, depth: int = 3, MCd: bool = False):
#         super(Net, self).__init__()
#         self.MCd = MCd
#
#         self.init_conv = nn.Sequential(
#             nn.Conv2d(1, 64, kernel_size=3, stride=2, padding=1),
#             nn.BatchNorm2d(64),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
#         )
#
#         layers = []
#
#         in_channels = 64
#
#         for i in range(depth):
#             out_channels = in_channels * 2 if i else in_channels  # Double the channels at each layer, but not for the first
#             layers.append(ResidualBlock(in_channels, out_channels, stride=2 if i else 1, apply_dropout = True),)
#             layers.append(ResidualBlock(out_channels, out_channels, apply_dropout = True))  # Keep the same number of channels within a layer
#             in_channels = out_channels
#
#         self.res_layers = nn.Sequential(*layers)
#
#         self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
#
#         # Assuming the output of the last ResidualBlock is `out_channels`, adjust linear layer accordingly.
#         self.linear_layers = nn.Sequential(
#             nn.Linear(out_channels, n_classes),
#         )
#
#     def forward(self, x):
#         x = self.init_conv(x)
#         x = self.res_layers(x)
#         x = self.avg_pool(x)
#         x = x.view(x.size(0), -1)
#
#         if self.MCd:
#             x = F.dropout(x, p=0.5)
#
#         x = self.linear_layers(x)
#
#         if self.MCd:
#             x = F.softmax(x, dim=1)  # Apply softmax to the output of the linear layer
#
#         return x


#Original Model
# class Net(nn.Module):
#     def __init__(self, n_classes: int) -> None:
#         super(Net, self).__init__()
#
#         self.cnn_layers = nn.Sequential(
#             # First 2D convolution layer
#             nn.Conv2d(1, 64, kernel_size=4, stride=1),
#             nn.BatchNorm2d(64),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=4),
#             torch.nn.Dropout(p=0.5, inplace=True),
#
#             # Second 2D convolution layer
#             nn.Conv2d(64, 32, kernel_size=4, stride=1),
#             nn.BatchNorm2d(32),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=3),
#             torch.nn.Dropout(p=0.25, inplace=True),
#
#             # Third 2D convolution layer
#             nn.Conv2d(32, 16, kernel_size=4, stride=1),
#             nn.BatchNorm2d(16),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=2),
#             torch.nn.Dropout(p=0.125, inplace=True),
#
#             nn.AdaptiveAvgPool2d((1, 1))
#         )
#
#         self.linear_layers = nn.Sequential(
#             nn.Flatten(),  # Flatten the output of adaptive avg pooling
#             nn.Linear(16, 256),  # Adjust input size based on the actual output of CNN
#             nn.Linear(256, n_classes),
#             nn.Softmax(dim=1)
#         )
#
#     # Defining the forward pass
#     def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
#         # x = self.cnn_layers(x)
#         # # After our convolutional layers which are 2D, we need to flatten our
#         # # input to be 1 dimensional, as the linear layers require this.
#         # x_prediction = x.view(x.size(0), -1)
#         # x = self.linear_layers(x_prediction)
#         # return x
#         x = self.cnn_layers(x)
#         x = self.linear_layers(x)
#         return x  # Directly return logits for compatibility with CrossEntropyLoss
#
#
#
#
#
# class Net(nn.Module):
#     def __init__(self, n_classes: int) -> None:
#         super(Net, self).__init__()
#
#         self.cnn_layers = nn.Sequential(
#             # Defining a 2D convolution layer
#             nn.Conv2d(1, 64, kernel_size=4, stride=1),
#             nn.BatchNorm2d(64),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=4),
#             torch.nn.Dropout(p=0.5, inplace=True),
#             # Defining another 2D convolution layer
#             nn.Conv2d(64, 32, kernel_size=4, stride=1),
#             nn.BatchNorm2d(32),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=3),
#             torch.nn.Dropout(p=0.25, inplace=True),
#             # Defining another 2D convolution layer
#             nn.Conv2d(32, 16, kernel_size=4, stride=1),
#             nn.BatchNorm2d(16),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=2),
#             torch.nn.Dropout(p=0.125, inplace=True),
#         )
#
#         self.linear_layers = nn.Sequential(
#             nn.Linear(144, 256),
#             nn.Linear(256, n_classes)
#         )
#
#     # Defining the forward pass
#     def forward(self, x: torch.Tensor) -> torch.Tensor:
#         x = self.cnn_layers(x)
#         # After our convolutional layers which are 2D, we need to flatten our
#         # input to be 1 dimensional, as the linear layers require this.
#         x = x.view(x.size(0), -1)
#         x = self.linear_layers(x)
#         return x


# class Net(nn.Module):
#     def __init__(self, n_classes: int) -> None:
#         super(Net, self).__init__()
#
#         self.cnn_layers = nn.Sequential(
#             # First 2D convolution layer
#             nn.Conv2d(1, 64, kernel_size=4, stride=1),
#             nn.BatchNorm2d(64),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=4),
#             torch.nn.Dropout(p=0.5, inplace=True),
#
#             # Second 2D convolution layer
#             nn.Conv2d(64, 32, kernel_size=4, stride=1),
#             nn.BatchNorm2d(32),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=3),
#             torch.nn.Dropout(p=0.25, inplace=True),
#
#             # Third 2D convolution layer
#             nn.Conv2d(32, 16, kernel_size=4, stride=1),
#             nn.BatchNorm2d(16),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=2),
#             torch.nn.Dropout(p=0.125, inplace=True),
#
#             nn.AdaptiveAvgPool2d((1, 1))
#         )
#
#         self.linear_layers = nn.Sequential(
#             nn.Flatten(),  # Flatten the output of adaptive avg pooling
#             nn.Linear(16, 256),  # Adjust input size based on the actual output of CNN
#             nn.Linear(256, n_classes),
#             nn.Softmax(dim=1)
#         )
#
#     # Defining the forward pass
#     def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
#         # x = self.cnn_layers(x)
#         # # After our convolutional layers which are 2D, we need to flatten our
#         # # input to be 1 dimensional, as the linear layers require this.
#         # x_prediction = x.view(x.size(0), -1)
#         # x = self.linear_layers(x_prediction)
#         # return x
#         x = self.cnn_layers(x)
#         x = self.linear_layers(x)
#         return x  # Directly return logits for compatibility with CrossEntropyLoss
#
#
#
#
#
# class ResidualBlock(nn.Module):
#     def __init__(self, in_channels, out_channels, stride=1, expansion=1):
#         super(ResidualBlock, self).__init__()
#         mid_channels = out_channels // expansion
#         self.conv1 = nn.Conv2d(in_channels, mid_channels, kernel_size=3, stride=stride, padding=1)
#         self.bn1 = nn.BatchNorm2d(mid_channels)
#         self.relu = nn.ReLU(inplace=True)
#
#         self.conv2 = nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1)
#         self.bn2 = nn.BatchNorm2d(out_channels)
#
#         self.downsample = nn.Sequential()
#         if stride != 1 or in_channels != out_channels:
#             self.downsample = nn.Sequential(
#                 nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride),
#                 nn.BatchNorm2d(out_channels)
#             )
#
#     def forward(self, x):
#         identity = self.downsample(x)
#
#         out = self.conv1(x)
#         out = self.bn1(out)
#         out = self.relu(out)
#
#         out = self.conv2(out)
#         out = self.bn2(out)
#
#         out += identity
#         out = self.relu(out)
#
#         return out


# class Net(nn.Module):
#     def __init__(self, n_classes: int, depth: int = 3):
#         super(Net, self).__init__()
#
#         self.init_conv = nn.Sequential(
#             nn.Conv2d(1, 64, kernel_size=3, stride=2, padding=1),
#             nn.BatchNorm2d(64),
#             nn.ReLU(inplace=True),
#             nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
#         )
#
#         layers = []
#         in_channels = 64
#         for i in range(depth):
#             out_channels = in_channels * 2 if i else in_channels  # Double the channels at each layer, but not for the first
#             layers.append(ResidualBlock(in_channels, out_channels, stride=2 if i else 1))
#             layers.append(ResidualBlock(out_channels, out_channels))  # Keep the same number of channels within a layer
#             in_channels = out_channels
#
#         self.res_layers = nn.Sequential(*layers)
#
#         self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
#         # Assuming the output of the last ResidualBlock is `out_channels`, adjust linear layer accordingly.
#         self.linear_layers = nn.Sequential(
#             nn.Linear(out_channels, n_classes),
#         )
#
#     def forward(self, x):
#         x = self.init_conv(x)
#         x = self.res_layers(x)
#         x = self.avg_pool(x)
#         x = x.view(x.size(0), -1)
#         x = self.linear_layers(x)
#         return x