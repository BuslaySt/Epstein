# import ctypes
# from picosdk.ps3000a import ps3000a as ps
# from picosdk.functions import adc2mV, assert_pico_ok

import numpy as np
import scipy as sp
import pandas as pd

import math, time
# import matplotlib.pyplot as plt
from serial import Serial

from pico3204D import Picoscope3204D


def getFFT(voltage):
    an = []
    bn = []
    duration = 0.01
    sampleRate = 50000
    n = int(duration*sampleRate)
    F = sp.fft.rfft(voltage)
    #freqs = sp.fft.rfftfreq(n, 1/sampleRate)
    
    for num in range(0, 7):
        an.append(2*np.real(F[num]) /n)
        bn.append(-2*np.imag(F[num]) /n)
    print('FFT done')
    return (an, bn, F)
 
def genSinewave(freq, amp, t):
    sinewave = 0.01*amp*np.sin(2*np.pi*freq*t)
    return sinewave

def genHarm(i, freq, amp, t, frac):
    additionalSignal = 0.0001*frac*amp*np.sin(2*np.pi*(i+2)*freq*t)
    
    return additionalSignal

def genModulations(i, voltage):
    F = sp.fft.rfft(voltage)
    F_corr = F.copy()
    F_corr[i] = -F[i]
    modSignal = sp.fft.irfft(F_corr).real

    return modSignal

def loadGen(signal):
    waveform = [int(signal[n]*32767) for n in range(0, len(signal))]
    
    for point in waveform:
        value = point.to_bytes(2, 'big', signed = 'True')
        serialData.write(value)
    print('Data load to gen done')

def zero():
    zeroe = 0
    for n in range(0, 1000):
        res = zeroe.to_bytes(2, 'big')
        serialData.write(res)

def create_gaussian_peak(size=1000, center=500, amplitude=1, sigma=10):
    """
    Создает массив с гауссовым пиком
    
    Parameters:
    size: размер массива
    center: центр пика (0-индексированный)
    amplitude: амплитуда пика
    sigma: стандартное отклонение (ширина пика)
    """
    x = np.arange(size)
    arr = amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))
    return arr

def calculate_thd(Fourier_series):
    numerator = 0
    for i in range (2, len(Fourier_series)):
        numerator += (math.pow(np.abs(Fourier_series[i]), 2))

    thd = 100*math.sqrt(numerator)/(np.abs(Fourier_series[1]))

    return thd


def expand_coefficients_dataframe(df):
    """
    Преобразует датафрейм с вложенными списками коэффициентов в плоскую структуру.
    Возвращает:
    Новый датафрейм с отдельными колонками для каждого коэффициента
    """
    # Определяем количество коэффициентов (n)
    n = len(df['coefA_in'].iloc[0])
    
    # Создаем новый датафрейм с базовыми колонками
    new_df = df[['freq', 'amp', 'THD_out']].copy()
    
    # Добавляем колонки для каждого коэффициента
    for i in range(n):
        new_df[f'coefA_in_{i}'] = df['coefA_in'].apply(lambda x: x[i])
        new_df[f'coefB_in_{i}'] = df['coefB_in'].apply(lambda x: x[i])
        new_df[f'coefA_out_{i}'] = df['coefA_out'].apply(lambda x: x[i])
        new_df[f'coefB_out_{i}'] = df['coefB_out'].apply(lambda x: x[i])
    return new_df

#---------------------------------------------------------------------------------------#
picoscope = Picoscope3204D()
picoscope.initialize_ports(channelA_range=10, channelB_range=7)

fsamp = 50000
duration = 0.02
N = int(fsamp*duration)
t = np.linspace(0, duration, N)

serialData = Serial('COM5', baudrate=115200)
coefA_out = []
coefB_out = []
coefA_in = []
coefB_in = []
res = []

zero() # обнуление генератора
iterations = 20
freqs = np.arange(50, 400, 50) # от 50 до 400 с шагом 50
startAmp = 10
amp = startAmp

for freq in freqs:
    signal = genSinewave(freq, amp, t)
    
    for i in range(0, iterations):
        loadGen(signal)
        time.sleep(0.1)
        voltage = picoscope.read_data(max_samples=1000, sample_rate=2502).ch_B # read_data возвращает три столбца - 'time' : time_axis, 'ch_A' : adc2mVChAMax, 'ch_B' : adc2mVChBMax
        # coefA_in, coefB_in.append(getFFT(signal)) ломало вывод data
        # coefA_out, coefB_out.append(getFFT(voltage)) ниже исправление
        an_in, bn_in, F_in = getFFT(signal)        #
        an_out, bn_out, F_out = getFFT(voltage)     #
        ######################################
        thd_out = calculate_thd(F_out)
        res.append({
            "freq": freq, 
            "amp": amp, 
            "coefA_in": an_in, 
            "coefB_in": bn_in, 
            "coefA_out": an_out, 
            "coefB_out": bn_out,
            "THD_out": thd_out
            })
        frac = np.random.randint(100)
        amp = np.random.randint(20)
        peak_pos = np.random.randint(1000)
        peak = create_gaussian_peak(1000, center=peak_pos, amplitude=amp/500, sigma=15)
        harm = genHarm(i, freq, amp, t, frac)
        signal = signal + harm + peak # + genModulations(i, voltage) #тут можно убрать genModulations, она может привести к совершенно кривому варианту на выходе
        time.sleep(0.5)
    freq+=50
    

zero() # обнуление генератора
picoscope.close()

data = pd.DataFrame(res)
data.to_csv(f"data_{time.strftime("%Y-%m-%d_%H-%M")}.csv")
# data.to_csv('data.csv')
    
expdata = expand_coefficients_dataframe(data)
expdata.to_csv(f"expdata_{time.strftime("%Y-%m-%d_%H-%M")}.csv")