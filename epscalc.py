import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from icecream import ic
import epscalc

#v1.3

#ic.disable()

#основной скрипт вычисления и вывода графиков
def run (runParameters):
    '''
    l = 0.39 длина полосы стали, константа для данного аппарата Эпштейна.
    Остальные параметры образцов стали задаются пользователем и передаются функции в test_parameters
    configNumber - конфигурация обмоток. 1 - полная, 4 - одна четверть
    '''
    
    #!!константы для данной реализации измерительной установки
    l = 390/1000 #длина полосы стали, константа для образца аппарата Эпштейна
    measuringCoilCount = 50 #количество витков в измерительной катушке
    
    df, freq, key, configNumber, test_parameters = runParameters
    
    coilCoef = 4*measuringCoilCount # 4 измерительных катушки в рамке 
    x, y, N, ro = test_parameters

    currentCoef = 1.00 # коэффициент датчика тока
    ersted2Am = 9.8*79.57 #пересчет из Эрстед в А/м, 9.8 - множитель для конкретного набора катушек
    match configNumber:
        case 1: #150:50
            configCoef = (0.75*ersted2Am)
            ratio = 3 
        case 2: #100:50
            configCoef = (0.5*ersted2Am)
            ratio = 2
        case 3: #50:50
            configCoef = (0.25*ersted2Am)
            ratio = 1
    
    bCoef = N*x*y #приведение потока к индукции
    coefSet = [currentCoef, configCoef, bCoef, coilCoef]
    timeset = 10**9 #
    period = timeset//freq
    ic(period)
    time_coef = 10**-9 
    time = df['time'].values
    dx = (time_coef*(time[1] - time[0]))  
    samplingTime = (time[-1] - time[0])
    ic(samplingTime)
    period_number = int(samplingTime//period)
    ic(period_number)
    startIndices, finishIndices = epscalc.get_periods(df, period_number, period)
    ic(len(startIndices))
    integratedValues, H_fieldValues, currentValues, voltageValues = epscalc.voltage_integration(df, startIndices, finishIndices, dx, coefSet)
    ic(len(integratedValues))
    avgInt = epscalc.array_averaging(integratedValues)
    avgH_field = epscalc.array_averaging(H_fieldValues)
    avgCurrent = epscalc.array_averaging(currentValues)
    avgVoltage = epscalc.array_averaging(voltageValues)

    currentOffset = np.mean(avgCurrent)
    corrCurrent = np.array(avgCurrent) - currentOffset
    H_fieldOffset = np.mean(avgH_field)
    corrH_field = np.array(avgH_field) - H_fieldOffset
    
    Bmax = max(avgInt)
    Imax = max(corrCurrent)
    Imin = min(corrCurrent)
    Vmax = max(avgVoltage)
    Vmin = min(avgVoltage)
    
    # if abs(Vmax + Vmin) > 0.1*Vmax or abs(Imax + Imin) > 0.1*Imax:
    #     line = '-'*25
    #     print(line, "Выявлен перекос амплитуд!", line, sep='\n')
    #     print(Imax)
    #     print(Imin)
    #     print(Vmax)
    #     print(Vmin)

    Iabsmax = max(Imax, -Imin)
    Vabsmax = max(Vmax, -Vmin)

    powerLosses = 0
    if key == 1:
        mass = 4*N*x*y*l*ro
        ic(mass)
        powerLosses = epscalc.powerloss_calculation(corrCurrent, avgVoltage, currentCoef)*ratio/mass

    return Bmax, corrH_field, avgInt, powerLosses, Iabsmax, Vabsmax


#функция определения индексов начала и конца периодов
def get_periods (df, period_number, period):

    startIndex = 0
    finishIndex = 0
    startIndices = []
    finishIndices = []

    for num in range(0, period_number):
        startIndices.append(startIndex)
        startTime = df['time'].loc[startIndex]
        finishTime = startTime + period
        
        for i in df.index:
            if abs(df['time'][i] - finishTime) < 500: #1
                finishIndex = i
            
        finishIndices.append(finishIndex)
        startIndex = finishIndex
    
    return (startIndices, finishIndices)

#функция измерения потерь
def powerloss_calculation (avgCurrent, avgVoltage, currentCoef):
    current = []
    voltage = []
        
    current = np.array(avgCurrent)
    voltage = np.array(avgVoltage)
    avgLosses = np.mean(current*voltage*currentCoef)

    return (avgLosses)    
        
#функция вывода всех периодов тока и интегрирования отдельных периодов
def voltage_integration(df, startIndices, finishIndices, dx, coefSet):
    
    #coefSet[0] - current sensing
    #coefSet[1] - coil config and current to H
    #coefSet[2] - voltage to B
    allInt = []
    allCurrent = []
    allH_field = []
    allVoltage = []
    
    for start, finish in zip(startIndices, finishIndices):
        df_period = (df[start:finish].reset_index(drop = True))
        voltage = df_period['ch_B'].values/1000 #приведение к В
        current = df_period['ch_A'].values/1000 #приведение к A
        n = len(voltage) - 1
        allH_field.append(current*coefSet[0]*coefSet[1])
        allCurrent.append(current)
        allVoltage.append(voltage)
        intVal = []
        startValue = 0
    
        intVal = epscalc.trapezoidal_integration (n, voltage, dx)
        
        corrInt = epscalc.minus_integration(intVal)
        zeroValue = sum(corrInt)/len(corrInt)
            
        finInt = []
        for value in corrInt:
            finInt.append((value-zeroValue)/(coefSet[2]*coefSet[3]))

        finInt.insert(0, -zeroValue/(coefSet[2]*coefSet[3]))
        allInt.append(finInt)

    return (allInt, allH_field, allCurrent, allVoltage)

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

    df = pd.read_csv('rawdata_2025-04-03_12-43_50000@50Hz_1500mV.csv', sep = ',')

    key = 1 #показатель вычисления потерь, должен запускаться на индукции насыщения
    
    freq = 50
    configNumber = 1
    x = 0.25/1000
    y = 30/1000
    N = 1
    ro = 7830
    
    #plt.plot(df.ch_A)
    #plt.plot(df.ch_B)
    sampleParameters = [x, y, N, ro]
    runParameters = [df, freq, key, configNumber, sampleParameters]
    Bmax, avgCurrent, avgInt, powerLosses = epscalc.run (runParameters)
    epscalc.graph(avgCurrent, avgInt)
    ic.enable()
    ic(Bmax)
    ic(powerLosses)
    #plt.show()
