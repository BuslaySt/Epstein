#service module for rotating coil and Epstein software
#v. 0.1 July 2025
import numpy as np
import math
from tqdm import tqdm   # Progress bar


def array_averaging (allPeriod) -> tuple:
  
    '''
    Функция выполняет вычисление усредненного значения интегралов 
    по нескольким периодам через транспонирование двумерного списка.			
     ------------------------------------------------------------------------------------
    Переменные
        
        allPeriod : list
            Двумерный список. Каждая строка списка представляет собой 
            отдельный список, являющийся интегрированным сигналом 
            по одному периоду датафрейма. 

    ''' 
    
    avgArr = []
    arr = np.asarray(allPeriod)
    arrTransp = arr.transpose()
    avgArr = [sum(item)/len(arr) for item in arrTransp]

    return (avgArr)

def minus_integration (integral_list):
    '''
    Функция убирает постоянную составляющую после интегрирования. 
    ------------------------------------------------------------------------------------
    Переменные
    
        integral_list : list
            Список с отметками интегрированного сигнала по одному периоду из всего 
            датафрейма. Применяется к каждому периоду из датафрейма.
            
    '''
   
    corrected_integral = []
    delta = integral_list[-1] - integral_list[0]
    corrected_integral = [(value - delta*(i+1)/len(integral_list)) for i, value in enumerate(integral_list)]
    
    return corrected_integral

def minus_constant (input_channel, zeroPos_start, zeroPos_end):
    '''
    Функция убирает постоянную составляющую из входного сигнала. 
    ------------------------------------------------------------------------------------
    Переменные
    
        input_channel : столбец датафрейма
            Наименование столбца из входного датафрейма, 
            к которому применяется коррекция
        zeroPos_start : int
            Индекс строки датафрейма, в которой зарегистрирован 
            первый нулевой импульс энкодера в датафрейме
        zeroPos_end : int
            Индекс строки датафрейма, в которой зарегистрирован 
            последний нулевой импульс энкодера в датафрейме     
    '''
    '''
    
    ch_name = input_channel.to_numpy()
    constant = np.mean(ch_name)
    data_stream = np.array(ch_name)
    channel_name_norm = data_stream - constant
    
    #old code
    constant = sum(input_channel[k] for k in range (zeroPos_start, zeroPos_end + 1))/ ((zeroPos_end+1)-zeroPos_start) 
    channel_name_norm = []   
    for i in tqdm(range(zeroPos_start, zeroPos_end + 1), desc = 'Коррекция постоянной составляющей во входном сигнале'):
        channel_name_norm.append(input_channel[i] - constant)
    
    #new code
    constant = sum(input_channel[zeroPos_start:zeroPos_end + 1])/ len(input_channel[zeroPos_start:zeroPos_end + 1])
    channel_name_norm = []   
    for i in tqdm(range(zeroPos_start, zeroPos_end + 1), desc = 'Проводится коррекция входного сигнала...'):
        channel_name_norm.append(input_channel[i] - constant)
    '''
    constant = sum(input_channel[zeroPos_start:zeroPos_end + 1])/ len(input_channel[zeroPos_start:zeroPos_end + 1])
    channel_name_norm = [(input_channel[n] - constant) for n in tqdm(range(zeroPos_start, zeroPos_end + 1))]

    return channel_name_norm
