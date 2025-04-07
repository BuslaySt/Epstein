import sys
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import epscalc
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
        # self.pBtn_init.clicked.connect(self.init_pico)
        self.pBtn_start.clicked.connect(self.start)
        self.pBtn_save.clicked.connect(self.save)
        
        #график
        self.graphWidget.setBackground('w')

    def init_pico(self):
        '''- Инициализация осциллографа Picoscope3204D и подключение портов -'''
        self.picoscope = Picoscope3204D()
        self.picoscope.initialize_ports()

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

        self.amp = 500000 # начальная амплитуда в мкВ
        key = 0 # соответствие измеренной Вм и заданной Вм меняется на 1 по достижении заданной величины индукции, запускает измерение потерь.

        try:
            # цикл увеличения амплитуды генератора до достижения целевой индукции
            while not key:
                self.amp += 100000
                self.picoscope.setup_generator(self.freq, amplitude=self.amp)

                samples = int(5*100000/self.freq)
                self.data = self.picoscope.read_data(max_samples=samples, sample_rate=timebase)

                # Проверка выхода за пределы каналов
                self.

                sampleParameters = [x, y, N, ro]
                runParameters = [self.data, self.freq, key, configNumber, sampleParameters]
                result = epscalc.run(runParameters)
                Bmax = result[0]
                
                print(Bmax)
                if Bmax >= B or self.amp >= 2000000:
                    key = 1
                

            self.picoscope.setup_generator(self.freq, amplitude=self.amp)
            samples = int(30*100000/self.freq)
            self.data = self.picoscope.read_data(max_samples=samples, sample_rate=timebase)

            sampleParameters = [x, y, N, ro]
            runParameters = [self.data, self.freq, key, configNumber, sampleParameters]
            result = epscalc.run(runParameters)
            self.Bmax = result[0]
            self.H = result[1]
            self.B = result[2]
            self.powerLosses = result[3]
            
            print(self.Bmax, self.powerLosses)
            self.plotData()
        except Exception as e:
            print(f"Что-то пошло не так: {e}")

    def save(self):
        # Обработка нажатия кнопки "Сохранить результат"
        try:
            self.picoscope.save_data(self.data, self.freq, self.amp)
            print("Результат сохранён")
        except Exception as e:
            print(f"Что-то пошло не так: {e}")

    def plotData(self):
        self.graphWidget.clear()       
        styles = {'color': 'black', 'font-size': '12px'}
        self.graphWidget.setLabel('left', "B", **styles)
        self.graphWidget.setLabel('bottom', "H", **styles)
        self.graphWidget.showGrid(x = True, y = True)
        self.graphWidget.setXRange(min(self.H), max(self.H))
        self.graphWidget.setYRange(min(self.B), max(self.B))
        self.pltData = self.graphWidget.plot(x = self.H, y = self.B, pen = 'b')#, symbol = 'o')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    epstein = MainUI()
    epstein.show()

    try:
        epstein.init_pico()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        epstein.picoscope.close()
        print(f"pico closed")


