import sys
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import epscalc
import time
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
        # Подключаем обработчики событий
        self.pBtn_init.clicked.connect(self.init_pico)
        self.pBtn_start.clicked.connect(self.start)
        self.pBtn_save.clicked.connect(self.save)

        '''//ИП
        секция графика пока не в окончательном состоянии - возможны манипуляции
        '''
        #график
        self.graphWidget.clear()
        self.graphWidget.setBackground('w')
        #all hist data
        self.allH = []
        self.allB = []

    def init_pico(self):
        '''- Инициализация осциллографа Picoscope3204D и подключение портов -'''
        # self.picoscope = Picoscope3204D()
        self.limitA = 5
        self.limitB = 7
        self.picoscope.initialize_ports(limitA=self.limitA, limitB=self.limitB)
        self.freq = int(self.lEd_f.text().replace(',','.')) # частота генератора, Гц
        self.amp = 500000 # начальная амплитуда в мкВ
        self.picoscope.setup_generator(self.freq, amplitude=self.amp)

    def start(self):
        '''- Измерения -'''
        # При нажатии кнопки "Начать измерения" запускаем цикл измерений
        print("Начало измерений")
        # Рабочая частота и целевая индукция задаются пользователем в интерфейсе
        self.freq = int(self.lEd_f.text().replace(',','.')) # частота генератора, Гц
        timebase=1252 # timebase=1252 == 10 мкс
        B = float(self.lEd_B.text().replace(',','.')) # магнитная индукция, Тл
        configNumber = int(self.cBox_conf.currentText()) # номер конфигурации катушек на выбор 1 из 3, выбор из списка

        # Параметры пластин из интерфейса задаются пользователем
        x = float(self.lEd_x.text().replace(',','.'))/1000 # толщина, мм в м
        y = float(self.lEd_y.text().replace(',','.'))/1000 # ширина, мм в м
        N = int(self.lEd_N.text().replace(',','.')) # количество слоев полос, уложенных в рамку
        ro = float(self.lEd_ro.text().replace(',','.')) # плотность материала

        self.limitA = 5 # 500mV на канал А
        self.limitB = 7 # 2V на канал B
        self.picoscope.initialize_ports(limitA=self.limitA, limitB=self.limitB)

        self.amp = 500000 # начальная амплитуда в мкВ
        key = 0 # соответствие измеренной Вм и заданной Вм меняется на 1 по достижении заданной величины индукции, запускает измерение потерь.

        try:
            # цикл увеличения амплитуды генератора до достижения целевой индукции
            while not key:
                self.amp += 50000
                self.picoscope.initialize_ports(limitA=self.limitA, limitB=self.limitB)
                self.picoscope.setup_generator(self.freq, amplitude=self.amp)

                samples = int(5*100000/self.freq)
                self.data = self.picoscope.read_data(max_samples=samples, sample_rate=timebase)
                time.sleep(0.002)
                # Проверка выхода за пределы каналов
                check = self.picoscope.check_limits(self.data)
                if check == 1:
                    self.limitA += 1
                    self.amp -= 50000
                    continue
                elif check == 2:
                    self.limitB += 1
                    self.amp -= 50000
                    continue

                sampleParameters = [x, y, N, ro]
                runParameters = [self.data, self.freq, key, configNumber, sampleParameters]
                result = epscalc.run(runParameters)
                Bmax = result[0]
                
                print(Bmax)
                if Bmax >= B or self.amp >= 4000000:
                    key = 1
                
            self.picoscope.setup_generator(self.freq, amplitude=self.amp)
            samples = int(50*100000/self.freq)
            self.data = self.picoscope.read_data(max_samples=samples, sample_rate=timebase)

            sampleParameters = [x, y, N, ro]
            runParameters = [self.data, self.freq, key, configNumber, sampleParameters]
            result = epscalc.run(runParameters)
            self.Bmax = result[0]
            self.H = result[1]
            self.B = result[2]
            self.powerLosses = result[3]

            #all histeresis saved to file
            self.allH.append(H)
            self.allB.append(B)

            print(self.Bmax, self.powerLosses)
            self.plotData()
        except Exception as e:
            print(f"Что-то пошло не так: {e}")

    def save(self):
        # Обработка нажатия кнопки "Сохранить результат"
        try:
            self.picoscope.save_data(self.data, self.freq, self.amp)
            self.saveImg()
            print("Результат сохранён")
        except Exception as e:
            print(f"Что-то пошло не так: {e}")

    def plotData(self):
        # self.graphWidget.clear()
        styles = {'color': 'black', 'font-size': '12px'}
        self.graphWidget.setLabel('left', "B", **styles)
        self.graphWidget.setLabel('bottom', "H", **styles)
        self.graphWidget.showGrid(x = True, y = True)
        self.graphWidget.setXRange(min(self.H), max(self.H))
        self.graphWidget.setYRange(min(self.B), max(self.B))
        self.pltData = self.graphWidget.plot(x = self.H, y = self.B, pen = 'b')#, symbol = 'o')

    def saveImg(self):
        graphDir = 'graph'
        filename = time.strftime("%Y-%m-%d_%H-%M")
        os.makedirs(graphDir, exist_ok = True)
        # plt.plot(self.H, self.B, linewidth = 0.3, color = 'orange')
        plt.grid(visible = True, which = 'both', axis = 'both', color = 'grey', linestyle = ':', linewidth = 0.5)
        plt.xlabel("H")
        plt.ylabel("B")

        for H, B in zip(self.allH, self.allB):
            plt.plot(H, B, linewidth = 0.3, color = 'orange')
        
        plt.savefig(os.path.join(graphDir, f"{filename}_hister.jpg"), dpi = 600)
        plt.close()
        print('График сохранен успешно')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    epstein = MainUI()
    epstein.show()
    try:
        epstein.picoscope = Picoscope3204D()
        # epstein.init_pico()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(app.exec_())
    finally:
        epstein.picoscope.close()
        print(f"pico closed")