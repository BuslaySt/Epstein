import time, os, sys
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import epscalc
import matplotlib.pyplot as plt
from pico3204D import Picoscope3204D

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("epsdesign.ui", self)
        
        # Применяем стиль CSS
        qssFile="epsdesign.css"
        with open(qssFile,"r") as fqss:
            self.setStyleSheet(fqss.read())

        # Список конфигураций
        self.cBox_conf.addItems(['1','2','3'])
        # Подключаем обработчики событий на кнопки
        self.pBtn_init.clicked.connect(self.init_pico)
        self.pBtn_start.clicked.connect(self.start)
        self.pBtn_save.clicked.connect(self.save)
        self.pBtn_clear.clicked.connect(self.clear_interface)

        # секция графика пока не в окончательном состоянии - возможны манипуляции
        self.lists2zero() # обнуление списков с результатами серии измерений
        #график
        self.graphWidget.setBackground('w')
        
    def init_pico(self):
        ''' Инициализация осциллографа Picoscope3204D и подключение портов и генератора '''
        if not hasattr(self, 'picoscope'):
            self.picoscope = Picoscope3204D()
        
        # Подключение портов
        self.limitA = 5 # 500mV на канал А 
        self.limitB = 7 # 2V на канал B
        self.picoscope.initialize_ports(channelA_range=self.limitA, channelB_range=self.limitB)

        # Старт генератора
        self.freq = int(self.lEd_f.text().replace(',','.')) # частота генератора, Гц
        self.amp = 700000 #500000 # начальная амплитуда в мкВ
        self.picoscope.setup_generator(frequency=self.freq, amplitude=self.amp)

    def _message(self, message: str):
        ''' Вывод сообщений в консоль и статусбар '''
        print(message)
        self.statusBar.showMessage(message)

    def _amplificationIncrementCheck(self, Bmax, B) -> int:
        ''' Уменьшение шага прироста амплитуды в зависимости от разницы текущего и целевого значения индукции '''
        if abs(Bmax-B) < 0.2:
            ampincrement = self.freq*100
            print(f'Приращение 1 - {ampincrement/1000} мВ')
            return ampincrement
        elif abs(Bmax-B) < 0.5:
            ampincrement = self.freq*200
            print(f'Приращение 2 - {ampincrement/1000} мВ')
            return ampincrement
        elif abs(Bmax-B) < 1:
            ampincrement = self.freq*300
            print(f'Приращение 3 - {ampincrement/1000} мВ')
            return ampincrement
        ampincrement = self.freq*1000
        return ampincrement

    def start(self):
        ''' При нажатии кнопки "Начать измерения" запускаем цикл измерений '''
        self._message("Начало измерений")

        # Рабочая частота и целевая индукция задаются пользователем в интерфейсе
        self.freq = int(self.lEd_f.text().replace(',','.')) # частота генератора, Гц
        timebase=127 # timebase=1252 == 10 мкс 127 == 1 мкс
        B = float(self.lEd_B.text().replace(',','.')) # целевая магнитная индукция, Тл
        configNumber = int(self.cBox_conf.currentText()) # номер конфигурации катушек на выбор 1 из 3, выбор из списка

        self.lbl_Bmax.clear()
        self.lbl_powerLosses.clear()
        
        # Параметры пластин из интерфейса задаются пользователем
        x = float(self.lEd_x.text().replace(',','.'))/1000 # толщина, мм в м
        y = float(self.lEd_y.text().replace(',','.'))/1000 # ширина, мм в м
        N = int(self.lEd_N.text().replace(',','.')) # количество слоев полос, уложенных в рамку
        ro = float(self.lEd_ro.text().replace(',','.')) # плотность материала
        
        self.init_pico() # Реинициализация каналов и генератора

        key = 0 # соответствие измеренной Вм и заданной Вм меняется на 1 по достижении заданной величины индукции, запускает измерение потерь.
        step = 0
        ampincrement = 100000
        print(f'Приращение - {ampincrement/1000}')

        while True:
            # Проверка, что текущая индукция меньше целевой, если больше - уменьшаем амплитуду напряжения генератора
            samples = int(25*100000/self.freq) #50 - 127
            self.picoscope.initialize_ports(channelA_range=self.limitA, channelB_range=self.limitB)
            self.data = self.picoscope.read_data(max_samples=samples, sample_rate=timebase)

            match self.picoscope.check_limits(self.data):
                case 1:
                    if self.limitA < 10:
                        self.limitA += 1
                    else:
                        self._message("Достигнут предел по каналу A")
                        break
                    self.amp -= ampincrement
                    step -= 1
                    continue
                case 2:
                    if self.limitB < 10:
                        self.limitB += 1
                        print(self.limitB)
                    else:
                        self._message("Достигнут предел по каналу B")
                        break
                    self.amp -= ampincrement
                    step -= 1
                    continue

            sampleParameters = [x, y, N, ro]
            runParameters = [self.data, self.freq, key, configNumber, sampleParameters]
            result = epscalc.run(runParameters)
            Bmax = result[0]
            print(Bmax)
            if Bmax > B:
                self.amp -= ampincrement
                self.picoscope.setup_generator(frequency=self.freq, amplitude=self.amp)
            else:
                break

        ampincrement = self._amplificationIncrementCheck(Bmax, B)
        self.amp -= ampincrement

        try:
            # цикл увеличения амплитуды генератора до достижения целевой индукции
            while (not key) and (self.amp < 4000000) and (step < 200):
                step += 1
                print(f'Шаг:{step}')
                self.amp += ampincrement
                self.picoscope.initialize_ports(channelA_range=self.limitA, channelB_range=self.limitB)
                self.picoscope.setup_generator(frequency=self.freq, amplitude=self.amp)

                samples = int(25*100000/self.freq) #50
                self.data = self.picoscope.read_data(max_samples=samples, sample_rate=timebase)
                time.sleep(0.001)
                # Проверка выхода за пределы каналов
                match self.picoscope.check_limits(self.data):
                    case 1:
                        if self.limitA < 10:
                            self.limitA += 1
                        else:
                            self._message("Достигнут предел по каналу A")
                            break
                        self.amp -= ampincrement
                        step -= 1
                        continue
                    case 2:
                        if self.limitB < 10:
                            self.limitB += 1
                        else:
                            self._message("Достигнут предел по каналу B")
                            break
                        self.amp -= ampincrement
                        step -= 1
                        continue

                sampleParameters = [x, y, N, ro]
                runParameters = [self.data, self.freq, key, configNumber, sampleParameters]
                result = epscalc.run(runParameters)
                Bmax = result[0]
                print(Bmax)

                ampincrement = self._amplificationIncrementCheck(Bmax, B)

                if Bmax >= B:
                    key = 1

            self.picoscope.setup_generator(self.freq, amplitude=self.amp)
            samples = int(250*100000/self.freq)
            self.data = self.picoscope.read_data(max_samples=samples, sample_rate=timebase)

            sampleParameters = [x, y, N, ro]
            runParameters = [self.data, self.freq, key, configNumber, sampleParameters]
            result = epscalc.run(runParameters)
            self.Bmax = result[0]
            self.H = result[1]
            self.B = result[2]
            self.powerLosses = result[3]
            
            self.lbl_Bmax.setText(f'Индукция - {round(self.Bmax, 3)} Тл')
            self.lbl_powerLosses.setText(f'Потери - {round(self.powerLosses, 3)} Вт/кг')
            
            #all histeresis saved to file
            self.listOfH.append(self.H)
            self.listOfB.append(self.B)

            print(self.Bmax, self.powerLosses)
            self.BmaxList.append(round(self.Bmax, 3)) # правка для вывода таблицы
            self.PowerLossList.append(round(self.powerLosses, 3))
            self.plotData()

            if self.Bmax < B:
                message = "Целевое значение индукции не достигнуто"
            else:
                message = "Измерение завершено"
            self._message(message)

        except Exception as e:
            self._message(f"Что-то пошло не так при измерениях: {e}")

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
        self.listOfH = [] # все величины H для построения графиков при сохранении результата
        self.listOfB = [] # все величины В для построения графиков при сохранении результата
        self.BmaxList = [] # все величины Вм для построения графиков при сохранении результата
        self.PowerLossList = [] # все величины потерь для построения графиков при сохранении результата
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    try:
        epstein = MainUI()
        epstein.show()
        
        # epstein.init_pico()
        sys.exit(app.exec_())

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        if hasattr(epstein, 'picoscope') and epstein.picoscope:
            epstein.picoscope.close()
            print("Picoscope успешно закрыт")