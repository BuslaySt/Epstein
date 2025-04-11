import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from icecream import ic
from dataclasses import dataclass
from typing import Tuple, List, Optional

# Конфигурация отладки
ic.disable()

# Константы
EPSTEIN_FRAME_LENGTH = 0.39  # Длина полосы стали в метрах (константа аппарата Эпштейна)
MEASURING_COIL_TURNS = 50    # Количество витков в измерительной катушке
ERSTED_TO_AMPERES_PER_METER = 9.8 * 79.57  # Коэффициент пересчёта Эрстед в А/м
CURRENT_SENSING_COEF = 5     # Коэффициент измерения тока
TIME_CONVERSION_COEF = 1e-9  # Коэффициент перевода времени в секунды

@dataclass
class SampleParameters:
    """Параметры стального образца"""
    thickness: float    # Толщина (x), м
    width: float        # Ширина (y), м
    strips_per_layer: int  # Количество полос в слое (N)
    density: float      # Плотность материала (ro), кг/м³

@dataclass
class MeasurementConfig:
    """Конфигурация измерений"""
    frequency: float    # Частота, Гц
    calculate_losses: bool  # Флаг расчёта потерь
    winding_config: int  # Конфигурация обмоток (1-3)

class EpsteinCalculator:
    """
    Класс для расчёта характеристик стали по методу Эпштейна.
    
    Параметры:
        frame_length: Длина полосы стали в рамке Эпштейна (м)
        measuring_coil_turns: Количество витков измерительной катушки
    """
    
    def __init__(self, frame_length: float = EPSTEIN_FRAME_LENGTH, 
                 measuring_coil_turns: int = MEASURING_COIL_TURNS):
        self.frame_length = frame_length
        self.measuring_coil_turns = measuring_coil_turns
        self.coil_coef = 4 * measuring_coil_turns  # 4 измерительных катушки в рамке
        
    def calculate(self, data: pd.DataFrame, config: MeasurementConfig, 
                 sample: SampleParameters) -> Tuple[float, List[float], List[float], Optional[float]]:
        """
        Основной метод расчёта характеристик.
        
        Возвращает:
            Bmax: Максимальная индукция (Тл)
            avg_current: Усреднённые значения тока (А/м)
            avg_induction: Усреднённые значения индукции (Тл)
            power_losses: Удельные потери (Вт/кг), если calculate_losses=True
        """
        # Расчёт коэффициентов в зависимости от конфигурации обмоток
        config_coef, ratio = self._get_winding_coefficients(config.winding_config)
        
        # Расчёт коэффициентов для преобразования сигналов
        b_coef = sample.strips_per_layer * sample.thickness * sample.width
        coefficients = (CURRENT_SENSING_COEF, config_coef, b_coef, self.coil_coef)
        
        # Определение периодов сигнала
        period = 1 / config.frequency
        time_step = TIME_CONVERSION_COEF * (data['time'].iloc[1] - data['time'].iloc[0])
        period_count = int((data['time'].iloc[-1] - data['time'].iloc[0]) * config.frequency)
        
        start_indices, finish_indices = self._find_periods(data, period_count, period)
        
        # Интегрирование сигналов и расчёт характеристик
        integrated_values, current_values = self._integrate_voltage(
            data, start_indices, finish_indices, time_step, coefficients
        )
        
        avg_induction = self._average_arrays(integrated_values)
        avg_current = self._average_arrays(current_values)
        b_max = max(avg_induction)
        
        # Расчёт потерь (если требуется)
        power_losses = None
        if config.calculate_losses:
            mass = 4 * sample.strips_per_layer * sample.thickness * sample.width * self.frame_length * sample.density
            power_losses = self._calculate_power_losses(
                data, start_indices, finish_indices
            ) * ratio / mass
            
        return b_max, avg_current, avg_induction, power_losses
    
    def _get_winding_coefficients(self, config_number: int) -> Tuple[float, float]:
        """Возвращает коэффициенты для конкретной конфигурации обмоток"""
        configs = {
            1: (0.75 * ERSTED_TO_AMPERES_PER_METER, 3),  # 150:50
            2: (0.5 * ERSTED_TO_AMPERES_PER_METER, 2),    # 100:50
            3: (0.25 * ERSTED_TO_AMPERES_PER_METER, 1)    # 50:50
        }
        return configs.get(config_number, (0.0, 0.0))
    
    def _find_periods(self, data: pd.DataFrame, period_count: int, 
                     period: float) -> Tuple[List[int], List[int]]:
        """Находит индексы начала и конца каждого периода в данных"""
        start_indices = []
        finish_indices = []
        start_index = 100  # Пропускаем начальный переходный процесс
        
        for _ in range(period_count):
            start_indices.append(start_index)
            finish_time = data['time'].iloc[start_index] + period
            
            # Находим индекс ближайшего момента времени к finish_time
            finish_index = (data['time'] - finish_time).abs().idxmin()
            finish_indices.append(finish_index)
            start_index = finish_index
            
        return start_indices, finish_indices
    
    def _integrate_voltage(self, data: pd.DataFrame, start_indices: List[int], 
                          finish_indices: List[int], time_step: float, 
                          coefficients: Tuple[float, ...]) -> Tuple[List[List[float]], List[List[float]]]:
        """Интегрирует напряжение по периодам и преобразует в индукцию"""
        all_integrated = []
        all_current = []
        current_coef, config_coef, b_coef, coil_coef = coefficients
        
        for start, finish in zip(start_indices, finish_indices):
            period_data = data.iloc[start:finish].reset_index(drop=True)
            voltage = period_data['ch_B'].values / 1000  # мВ -> В
            current = period_data['ch_A'].values * (current_coef * config_coef / 1000)
            all_current.append(current)
            
            # Интегрирование методом трапеций
            integrated = self._trapezoidal_integration(voltage, time_step)
            corrected = self._correct_integration_drift(integrated)
            
            # Удаление постоянной составляющей и преобразование в индукцию
            dc_offset = np.mean(corrected)
            induction = [(value - dc_offset) / (b_coef * coil_coef) for value in corrected]
            induction.insert(0, -dc_offset / (b_coef * coil_coef))  # Добавляем начальное значение
            
            all_integrated.append(induction)
            
        return all_integrated, all_current
    
    @staticmethod
    def _trapezoidal_integration(signal: np.ndarray, step: float) -> List[float]:
        """Интегрирование методом трапеций"""
        integral = 0.0
        integrated_values = []
        
        for i in range(len(signal) - 1):
            integral += step * (signal[i] + signal[i + 1]) / 2
            integrated_values.append(integral)
            
        return integrated_values
    
    @staticmethod
    def _correct_integration_drift(integrated_values: List[float]) -> List[float]:
        """Коррекция дрейфа при интегрировании"""
        delta = integrated_values[-1] - integrated_values[0]
        n = len(integrated_values)
        return [value - delta * (i + 1) / n for i, value in enumerate(integrated_values)]
    
    @staticmethod
    def _average_arrays(arrays: List[List[float]]) -> List[float]:
        """Усреднение значений по нескольким периодам"""
        transposed = np.array(arrays).T
        return [np.mean(row) for row in transposed]
    
    def _calculate_power_losses(self, data: pd.DataFrame, 
                               start_indices: List[int], finish_indices: List[int]) -> float:
        """Расчёт потерь мощности"""
        currents = []
        voltages = []
        
        for start, finish in zip(start_indices, finish_indices):
            period_data = data.iloc[start:finish].reset_index(drop=True)
            currents.append(period_data['ch_A'].values)
            voltages.append(period_data['ch_B'].values)
        
        avg_current = self._average_arrays(currents)
        avg_voltage = self._average_arrays(voltages)
        
        # Расчёт средних потерь (в Вт)
        instantaneous_power = np.array(avg_current) * np.array(avg_voltage) * CURRENT_SENSING_COEF
        return np.mean(instantaneous_power) / 1e6  # Переводим в Вт

def plot_hysteresis_loop(current: List[float], induction: List[float]) -> None:
    """Построение петли гистерезиса"""
    plt.figure(figsize=(10, 6))
    plt.plot(current, induction)
    plt.xlabel('Напряжённость магнитного поля, A/м')
    plt.ylabel('Магнитная индукция, Тл')
    plt.title('Петля гистерезиса')
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    # Пример использования
    data = pd.read_csv('rawdata_2025-04-03_12-43_50000@50Hz_1500mV.csv')
    
    # Параметры образца
    sample = SampleParameters(
        thickness=0.25e-3,    # 0.25 мм
        width=30e-3,         # 30 мм
        strips_per_layer=1,
        density=7830         # кг/м³
    )
    
    # Конфигурация измерений
    config = MeasurementConfig(
        frequency=50,
        calculate_losses=True,
        winding_config=1
    )
    
    # Создание калькулятора и выполнение расчётов
    calculator = EpsteinCalculator()
    b_max, avg_current, avg_induction, losses = calculator.calculate(data, config, sample)
    
    # Визуализация результатов
    plot_hysteresis_loop(avg_current, avg_induction)
    
    # Вывод результатов
    ic.enable()
    ic(b_max)
    ic(losses)