import time, os, sys
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import epscalc, traceback
import matplotlib.pyplot as plt
from pico3204D import Picoscope3204D

class EpsteinFrameUI(QMainWindow):
    ''' Константы '''
    TIMEBASE = 127         # 1252 - 10 μs, 127 - 1 μs
    MAX_ATTEMPTS = 50     # Число попыток добраться до целевого значения
    NUMBER_OF_SAMPLES = 25*100000 # Базовое число сэмплов в настройках, x10 для измерения
    STARTAMP = 200000  # 200000 начальная амплитуда в мкВ
    AMPSTEP = 200000  # Стартовый шаг изменения амплитуды генератора в мкВ
    Ch_A_START = 2      # 50mV предел канала А для начала
    Ch_B_START = 4      # 200mV для канала B
                        # 0  == PS3000A_10MV:  ±10 mV - нет
                        # 1  == PS3000A_20MV:  ±20 mV - нет
                        # 2  == PS3000A_50MV:  ±50 mV
                        # 3  == PS3000A_100MV: ±100 mV
                        # 4  == PS3000A_200MV: ±200 mV
                        # 5  == PS3000A_500MV: ±500 mV
                        # 6  == PS3000A_1V:    ±1 V
                        # 7  == PS3000A_2V:    ±2 V
                        # 8  == PS3000A_5V:    ±5 V
                        # 9  == PS3000A_10V:   ±10 V
                        # 10 == PS3000A_20V:   ±20 V

    def __init__(self):
        super(EpsteinFrameUI, self).__init__()
        loadUi("epsdesign.ui", self)
        # Применяем стиль CSS
        qssFile="epsdesign.css"
        with open(qssFile,"r") as fqss:
            self.setStyleSheet(fqss.read())
        # Список конфигураций
        self.cBox_conf.addItems(['1','2','3'])
        # график
        self.graphWidget.setBackground('w')
        self.lists2zero() # обнуление списков с результатами серии измерений

        # Обработчики событий на кнопки
        self.pBtn_init.clicked.connect(self.init_pico)
        self.pBtn_start.clicked.connect(self.start)
        self.pBtn_save.clicked.connect(self.save)
        self.pBtn_clear.clicked.connect(self.clear_interface)

    def init_pico(self):
        ''' Инициализация осциллографа Picoscope3204D и подключение портов и генератора '''
        if not hasattr(self, 'picoscope'):
            self.picoscope = Picoscope3204D()
        
        # Подключение портов
        self.limitA = self.Ch_A_START
        self.limitB = self.Ch_B_START
        self.picoscope.initialize_ports(
            channelA_range=self.limitA,
            channelB_range=self.limitB
        )

        # Старт генератора
        self.freq = int(self.lEd_f.text().replace(',','.')) # частота генератора, Гц
        self.amp = self.STARTAMP #500000 начальная амплитуда в мкВ
        self.picoscope.setup_generator(frequency=self.freq, amplitude=self.amp)

    def _message(self, message: str):
        ''' Вывод сообщений в консоль и статусбар '''
        print(message)
        self.statusBar.showMessage(message)

    def _remove_outliers(self, series, threshold=3):
        ''' Удаление выбросов по Z-параметру '''
        median = series.median()
        mad = (series - median).abs().median()
        modified_z_score = 0.6745 * (series - median) / mad
        return series[modified_z_score < threshold]

    def _get_limits(self, max) -> int:
        ''' Выбор подходящего предела измерений по максимальной амплитуде сигнала '''
        if max < 50:
            return 2
        if max < 100:
            return 3
        if max < 200:
            return 4
        if max < 500:
            return 5
        if max < 1000:
            return 6
        if max < 2000:
            return 7
        if max < 5000:
            return 8
        if max < 10000:
            return 9
        if max < 20000:
            return 10

    def start(self):
        ''' Начать измерения по кнопке '''
        self._message("Начало измерений")

        ''' Получение параметров из интерфейса '''
        self.freq = int(self.lEd_f.text().replace(',','.'))  # частота генератора, Гц
        target_B = float(self.lEd_B.text().replace(',','.'))  # целевая магнитная индукция, Тл
        configNumber = int(self.cBox_conf.currentText())  # номер конфигурации катушек

        # Параметры пластины
        x = float(self.lEd_x.text().replace(',','.'))/1000  # толщина, мм в м
        y = float(self.lEd_y.text().replace(',','.'))/1000  # ширина, мм в м
        N = int(self.lEd_N.text().replace(',','.'))  # количество слоев
        ro = float(self.lEd_ro.text().replace(',','.'))  # плотность материала
        sampleParameters = [x, y, N, ro]

        self.lbl_Bmax.clear()
        self.lbl_powerLosses.clear()

        self.init_pico()  # Реинициализация каналов и генератора

        # Начальные параметры для метода маятника
        amp_step = self.AMPSTEP  # начальный шаг амплитуды
        direction = 1      # направление изменения (1 - увеличение, -1 - уменьшение)
        attempts = 0
        nWaves = 1
        max_attempts = self.MAX_ATTEMPTS  # максимальное количество итераций

        try:
            # Метод маятника для достижения целевой индукции
            while attempts < max_attempts:
                self.picoscope.initialize_ports(channelA_range=self.limitA, channelB_range=self.limitB)
                self.picoscope.setup_generator(frequency=self.freq, amplitude=self.amp)

                # Сбор данных
                samples = int(nWaves * self.NUMBER_OF_SAMPLES / self.freq)
                self.data = self.picoscope.read_data(max_samples=samples, sample_rate=self.TIMEBASE)
                
                # Проверка пределов измерения
                limits_check = self.picoscope.check_limits(self.data)
                if limits_check == 1 and self.limitA < 10:
                    self._message("Увеличиваем предел измерения канала A")
                    self.limitA += 1
                    continue
                elif limits_check == 2 and self.limitB < 10:
                    self._message("Увеличиваем предел измерения канала B")
                    self.limitB += 1
                    continue
                elif limits_check != 0:
                    self._message("Достигнут предел измерения")
                    break

                # Расчет текущей индукции
                runParameters = [self.data, self.freq, 0, configNumber, sampleParameters]
                result = epscalc.run(runParameters)
                current_B = result[0]
                self._message(f"Попытка {attempts}: Амплитуда={self.amp}, Шаг={amp_step}, Bmax={round(current_B, 3)} Тл")

                if abs(current_B - target_B) / target_B < 0.02:
                    break

                # Логика маятника
                if (current_B < target_B and direction > 0) or (current_B > target_B and direction < 0):
                    # Продолжаем движение в том же направлении
                    self.amp += direction * amp_step
                    if (direction * self.amp) >=  4000000:
                        self.amp = direction * 4000000
                        self._message("Достигнут максимум генератора (4V)")
                else:
                    # Меняем направление и уменьшаем шаг
                    direction *= -1
                    self._message('Разворот маятника')
                    nWaves += 1
                    amp_step = max(amp_step // 2, 1000)  # Уменьшаем шаг, но не меньше минимального
                    self.amp += direction * amp_step
                    
                attempts += 1

            # Тестовое измерение на большом количестве периодов и увеличенном пределе измерения
            self._message("Выполняем тестовое измерение...")
            self.limitA = max(self.limitA + 1, 10)
            self.limitB = max(self.limitB + 1, 10)
            self.picoscope.initialize_ports(channelA_range=self.limitA, channelB_range=self.limitB)
            nWaves = 5 # Число сэмплов увеличиваем в 5 раз от настроечного
            self.picoscope.setup_generator(self.freq, amplitude=self.amp)
            samples = int(nWaves * self.NUMBER_OF_SAMPLES / self.freq)
            self.data = self.picoscope.read_data(max_samples=samples, sample_rate=self.TIMEBASE)

            # Убираем выбросы
            self.data['ch_A'] = self._remove_outliers(self.data['ch_A'])
            self.data['ch_B'] = self._remove_outliers(self.data['ch_B'])
            print(f'Наличине выбросов A - {self.data.ch_A.isnull().sum()}')
            print(f'Наличине выбросов B - {self.data.ch_B.isnull().sum()}')
            self.data = self.data.interpolate()

            # Выбираем пределы каналов
            self.limitA = self._get_limits(self.data['ch_A'].abs().max())
            self.limitB = self._get_limits(self.data['ch_B'].abs().max())
                
            # Финальное измерение на большом количестве периодов
            self._message("Выполняем основное измерение...")
            self.picoscope.initialize_ports(channelA_range=self.limitA, channelB_range=self.limitB)
            nWaves = 10 # Число сэмплов увеличиваем в 10 раз от настроечного
            self.picoscope.setup_generator(self.freq, amplitude=self.amp)
            samples = int(nWaves * self.NUMBER_OF_SAMPLES / self.freq)
            self.data = self.picoscope.read_data(max_samples=samples, sample_rate=self.TIMEBASE)
            
            self.data['ch_A'] = self._remove_outliers(self.data['ch_A'])
            self.data['ch_B'] = self._remove_outliers(self.data['ch_B'])
            print(f'Наличине выбросов A - {self.data.ch_A.isnull().sum()}')
            print(f'Наличине выбросов B - {self.data.ch_B.isnull().sum()}')
            print(f'Предел канала A - {self.picoscope.POWER_RANGE[self.limitA]}, при максимуме амплитуды - {self.data['ch_A'].abs().max()}')
            print(f'Предел канала B - {self.picoscope.POWER_RANGE[self.limitB]}, при максимуме амплитуды - {self.data['ch_B'].abs().max()}')
            self.data = self.data.interpolate()

            # Финальный расчет
            runParameters = [self.data, self.freq, 1, configNumber, sampleParameters]
            result = epscalc.run(runParameters)
            self.Bmax = result[0]
            self.H = result[1]
            self.B = result[2]
            self.powerLosses = result[3]
            
            # Вывод результатов
            self.lbl_Bmax.setText(f'Индукция - {round(self.Bmax, 3)} Тл')
            self.lbl_powerLosses.setText(f'Потери - {round(self.powerLosses, 3)} Вт/кг')
            self._message(f'Финальный результат: Индукция - {round(self.Bmax, 3)} Тл; Потери - {round(self.powerLosses, 3)} Вт/кг')

            # Сохранение данных гистерезиса
            self.listOfH.append(self.H)
            self.listOfB.append(self.B)
            self.BmaxList.append(round(self.Bmax, 3))
            self.PowerLossList.append(round(self.powerLosses, 3))
            self.plotData()

            # Проверка достижения целевой индукции
            if abs(self.Bmax - target_B) / target_B > 0.05:  # допуск 5%
                self._message(f"Целевая индукция не достигнута. Получено {round(self.Bmax, 3)} Тл при цели {target_B} Тл")
            else:
                self._message(f"Измерение успешно завершено.")

        except Exception as e:
            self._message(f"Ошибка при измерениях: {str(e)}")
            print(f"Ошибка: {traceback.format_exc()}")

    def save(self):
        ''' Обработка нажатия кнопки "Сохранить результат" '''
        try:
            # self.picoscope.save_data(self.data, self.freq, self.amp)
            dataDir = 'data'
            filename = time.strftime("%Y-%m-%d_%H-%M")
            os.makedirs(dataDir, exist_ok = True)
            self.data.to_csv(os.path.join(dataDir, f"rawdata_{filename}@{self.freq}Hz_{int(self.amp/1000)}mV.csv"))
            self.saveImg()
            self._message('Данные сохранены')
            self.clear_interface()

        except Exception as e:
            self._message(f"Что-то пошло не так при сохранении: {e}")

    def plotData(self):
        ''' Вывод графика в GUI '''
        styles = {'color': 'black', 'font-size': '12px'}
        self.graphWidget.setLabel('left', "B", **styles)
        self.graphWidget.setLabel('bottom', "H", **styles)
        self.graphWidget.showGrid(x = True, y = True)
        self.graphWidget.setXRange(min(self.H), max(self.H))
        self.graphWidget.setYRange(min(self.B), max(self.B))
        self.pltData = self.graphWidget.plot(x = self.H, y = self.B, pen = 'b')#, symbol = 'o')

    def saveImg(self):
        ''' Сохранение картинки графика '''
        graphDir = 'graph'
        filename = time.strftime("%Y-%m-%d_%H-%M")
        os.makedirs(graphDir, exist_ok = True)
        # plt.plot(self.H, self.B, linewidth = 0.3, color = 'orange')
        plt.grid(visible = True, which = 'both', axis = 'both', color = 'grey', linestyle = ':', linewidth = 0.5)
        plt.xlabel("H")
        plt.ylabel("B")
        columnLabels = ['B', 'P']
        data = list(zip(self.BmaxList, self.PowerLossList))
        for H, B in zip(self.listOfH, self.listOfB):
            plt.plot(H, B, linewidth = 0.3, color = 'orange')
        plt.text(min(self.H), (self.Bmax - 0.2), f'f = {self.freq} Гц, Bmax = {round(self.Bmax, 2)} Тл, P = {round(self.powerLosses, 2)} Вт/кг', fontsize=7, bbox={'facecolor':'yellow','alpha':0.2})
        
        plt.text(min(self.H), (self.Bmax - 0.4), f'Конфигурация обмоток № {int(self.cBox_conf.currentText())}', fontsize=5, bbox={'facecolor':'yellow','alpha':0.2})
        plt.text(min(self.H), (self.Bmax - 0.6), f'Количество слоев N = {int(self.lEd_N.text().replace(',','.'))}', fontsize=5, bbox={'facecolor':'yellow','alpha':0.2})
        tab = plt.table(cellText = data, colWidths = [0.1]*2, colLabels = columnLabels, colColours = ['yellow']*2, loc = 'lower right')
        tab.set_fontsize(10)
        plt.savefig(os.path.join(graphDir, f"{filename}@{self.freq}Hz.jpg"), dpi = 600)
        plt.close()

    def clear_interface(self):
        ''' Очистка поля графика и текстовых полей '''
        self.graphWidget.clear() # очистка графика
        self.lbl_Bmax.clear()
        self.lbl_powerLosses.clear()
        self.lists2zero() # очистка списков с результатами измерений

    def lists2zero(self):
        ''' Очистка списков с результатами измерений '''
        self.listOfH = []       # все величины H для построения графиков при сохранении результата
        self.listOfB = []       # все величины В для построения графиков при сохранении результата
        self.BmaxList = []      # все величины Вм для построения графиков при сохранении результата
        self.PowerLossList = [] # все величины потерь для построения графиков при сохранении результата
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    try:
        epstein = EpsteinFrameUI()
        epstein.show()
        
        # epstein.init_pico()
        sys.exit(app.exec_())

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        if hasattr(epstein, 'picoscope') and epstein.picoscope:
            epstein.picoscope.close()
            print("Picoscope успешно закрыт")
