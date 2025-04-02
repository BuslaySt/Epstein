import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from icecream import ic
import epscalc

ic.disable()

#основной скрипт вычисления и вывода графиков
def run (df, freq, key):
    #инициализация параметров
    timeset = 10**9
    period = timeset/freq
    time_coef = 10**-9 
    time = df['time'].values
    dx = (time_coef*(time[1] - time[0]))  
    period_number = int((time[-1] - time[0])//period)
    
    startIndices, finishIndices = epscalc.get_periods(df, period_number, period)
    integratedValues, currentValues = epscalc.voltage_integration(df, startIndices, finishIndices, dx)

    avgInt = epscalc.array_averaging(integratedValues)
    avgCurrent = epscalc.array_averaging(currentValues)
    Bmax = max(avgInt)
    
    powerLosses = 0
    if key ==1:
        powerLosses = epscalc.powerloss_calculation(df, startIndices, finishIndices)


    return Bmax, avgCurrent, avgInt, powerLosses

#функция определения индексов начала и конца периодов
def get_periods (df, period_number, period):

    startIndex = 0
    finishIndex = 0
    startIndices = []
    finishIndices = []

    for num in range(0, period_number):
        startIndices.append(startIndex)
        startTime = df['time'].loc[startIndex]
        #ic(startTime)
        finishTime = startTime + period
        #ic(finishTime)

        for i in df.index:
            if abs(df['time'][i] - round(finishTime, 3)) < 0.0001:
                finishIndex = i
            #ic(finishIndex)
        finishIndices.append(finishIndex)
        startIndex = finishIndex
    
    return (startIndices, finishIndices)


def powerloss_calculation (df, startIndices, finishIndices):
    current = []
    voltage = []
    for start, finish in zip(startIndices, finishIndices):
        #ic(start, finish)
        df_period = (df[start:finish].reset_index(drop = True))
        current.append(df_period['ch_A'].values)
        voltage.append(df_period['ch_B'].values)
    
    avgCurrent = epscalc.array_averaging(current)
    avgVoltage = epscalc.array_averaging(voltage)
    power = []
    for i in range(len(avgCurrent)):
        power.append(avgCurrent[i]*avgVoltage[i]/10**6)
    
    avgLosses = sum(power)/len(power)

    return (avgLosses)    
        
#функция вывода всех периодов тока и интегрирования отдельных периодов
def voltage_integration(df, startIndices, finishIndices, dx):
    allInt = []
    current = []
    for start, finish in zip(startIndices, finishIndices):
        ic(start, finish)
        df_period = (df[start:finish].reset_index(drop = True))
        y = df_period['ch_B'].values/1000
        n = len(y) - 1
        current.append(df_period['ch_A'].values)

        intVal = []
        startValue = 0
    
        intVal = epscalc.trapezoidal_integration (n, y, dx)
        ic(len(intVal), sum(intVal))
        corrInt = epscalc.minus_integration(intVal)#print(intU)
        zeroValue = sum(corrInt)/len(corrInt)
        ic(zeroValue)
    
        finInt = []
        for value in corrInt:
            finInt.append(value-zeroValue)

        finInt.insert(0, -zeroValue)
        allInt.append(finInt)

    return (allInt, current)

#функция интегрирования методом трапеции
def trapezoidal_integration (n, y, dx):
      # Количество интервалов
    integral = 0
    intVal = []

    # Вычисление интеграла
    for i in range(n):
        integral += dx * (y[i] + y[i + 1])/2  # Метод трапеции
        intVal.append(integral)

    return intVal

#функция устранения ошибки интегрирования
def minus_integration (incomingInt):

    corrInt = []
    delta = incomingInt[-1] - incomingInt[0]
    
    for i, value in enumerate(incomingInt):
        corrInt.append(value - delta*(i+1)/(len(incomingInt)))
    
    return corrInt
#функция усреднения по нескольким периодам
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
    
    for item in arrTransp:
        avgArr.append(sum(item)/len(arr))
   
    return avgArr

#простой вывод графика
def graph(avgCurrent, avgInt):
    
    plt.plot(avgCurrent, avgInt)
    plt.grid()
    plt.show()


if __name__ == "__main__":

    key = 1 #показатель вычисления потерь, должен запускаться на индукции насыщения
    df = pd.read_csv('rawdata_2025-04-01_11-54_50Hz_10mks_1V.csv', sep = ',')
    Bmax, avgCurrent, avgInt, powerLosses = epscalc.run (df, 50, key)
    epscalc.graph(avgCurrent, avgInt)
    ic.enable()
    ic(Bmax)
    ic(powerLosses)