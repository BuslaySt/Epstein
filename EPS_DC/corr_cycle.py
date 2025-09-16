# import ctypes
# from picosdk.ps3000a import ps3000a as ps
# from picosdk.functions import adc2mV, assert_pico_ok

import numpy as np
import scipy as sp
import pandas as pd

import math, time
import matplotlib.pyplot as plt
from serial import Serial

from pico3204D import Picoscope3204D


def getFFT(voltage):
    an = []
    bn = []
    duration = 0.02
    sampleRate = 50000
    n = int(duration*sampleRate)
    FFT = sp.fft.rfft(voltage)
    FFTfreqs = sp.fft.rfftfreq(n, 1/sampleRate)
    
    for num in range(0, 50):
        an.append(2*np.real(FFT[num]) /n)
        bn.append(-2*np.imag(FFT[num]) /n)
    #print('FFT done')
    return (an, bn, FFT, FFTfreqs)
 
def genSinewave(freq, t):
    sinewave = np.sin(2*np.pi*freq*t)
    return sinewave

def genHarm(i, freq, amp, t, frac):
    additionalSignal = 0.0001*frac*amp*np.sin(2*np.pi*(i)*freq*t)
    
    return additionalSignal

def genModulations(voltage):
    F = sp.fft.rfft(voltage)
    F_corr = F.copy()
    n = np.random.randint(13)
    F_corr[n] = -F[n]
    modSignal = sp.fft.irfft(F_corr).real

    return modSignal

def loadGen(signal):
    waveform = [int((signal[n]/signal.max())*32767/7) for n in range(0, len(signal))]
    
    for point in waveform:
        value = point.to_bytes(2, 'big', signed = 'True')
        serialData.write(value)
    #print('Data load to gen done')

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
    if center > 500:
        amplitude = -amplitude
    arr = amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))
    return arr

def calculate_thd(Fourier_series, freq, base_freq):
    numerator = 0
    index_point = int(freq/base_freq)
    for i in range (index_point + 1, len(Fourier_series)):
        numerator += (math.pow(np.abs(Fourier_series[i]), 2))

    thd = 100*math.sqrt(numerator)/(np.abs(Fourier_series[index_point]))

    return thd


def expand_coefficients_dataframe(df):
    """
    Преобразует датафрейм с вложенными списками коэффициентов в плоскую структуру.
    Возвращает:
    Новый датафрейм с отдельными колонками для каждого коэффициента
    """
    # Определяем количество коэффициентов (n)
    n = len(df['coefA_out'].iloc[0])
    
    # Создаем новый датафрейм с базовыми колонками
    new_df = df[['freq', 'THD_out']].copy()
    
    # Добавляем колонки для каждого коэффициента
    for i in range(n):
        #new_df[f'coefA_in_{i}'] = df['coefA_in'].apply(lambda x: x[i])
        #new_df[f'coefB_in_{i}'] = df['coefB_in'].apply(lambda x: x[i])
        new_df[f'coefA_out_{i}'] = df['coefA_out'].apply(lambda x: x[i])
        new_df[f'coefB_out_{i}'] = df['coefB_out'].apply(lambda x: x[i])
    return new_df

#---------------------------------------------------------------------------------------#
serialData = Serial('COM5', baudrate=115200)
zero() # обнуление генератора
picoscope = Picoscope3204D()
picoscope.initialize_ports(channelA_range=10, channelB_range=9)

fsamp = 50000
duration = 0.02
N = int(fsamp*duration)
t = np.linspace(0, duration, N)
freq = 50
coef = 6/32767
base_freq = 50
harm_sign = genSinewave(freq, t)

for run in range(0, 50):
    print('Run number', run)
    
    loadGen(harm_sign)
    time.sleep(0.5)
    voltage = picoscope.read_data(max_samples=1000, sample_rate=2502).ch_B # read_data возвращает три столбца - 'time' : time_axis, 'ch_A' : adc2mVChAMax, 'ch_B' : adc2mVChBMax
    time.sleep(0.1)
    zero()
    
    #an_in, bn_in, F_in, FFTfreqs_in = getFFT(signal)
    an_out, bn_out, F_out, FFTfreqs_out = getFFT(voltage)
    THD = calculate_thd(F_out, freq, base_freq)
    print('THD = ', THD)
    
    ratio_31 = np.abs(F_out[3])/np.abs(F_out[1])
    ratio_51 = np.abs(F_out[5])/np.abs(F_out[1])
    ratio_71 = np.abs(F_out[7])/np.abs(F_out[1])
    print('ratio')
    print(ratio_31, ratio_51, ratio_71)
    phi_3 = math.atan(an_out[3]/bn_out[3])
    phi_5 = math.atan(an_out[5]/bn_out[5])
    phi_7 = math.atan(an_out[7]/bn_out[7])
    print(phi_3, phi_5, phi_7)
    harm_3 = ratio_31*np.sin(2*np.pi*3*freq*t - phi_3) #0.3
    harm_5 = ratio_51*np.sin(2*np.pi*5*freq*t - phi_5) #0.2
    harm_7 = ratio_71*np.sin(2*np.pi*7*freq*t - phi_7) #0.2
    harm_sign = harm_sign - 100*coef*harm_3# - 50*coef*harm_5 - 10*coef*harm_7
    time.sleep(0.5)

      
plt.plot(voltage)
plt.show()        

zero() # обнуление генератора
picoscope.close()

'''
data = pd.DataFrame(res)
print(data)
data.to_csv(f"dt_{time.strftime("%Y-%m-%d_%H-%M")}.csv")
#data.to_csv('data.csv')
print('data saved')    
expdata = expand_coefficients_dataframe(data)
expdata.to_csv(f"expdt_{time.strftime("%Y-%m-%d_%H-%M")}.csv")

'''