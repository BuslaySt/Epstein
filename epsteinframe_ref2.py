import sys
from PyQt5.QtWidgets import QMainWindow, QApplication, QProgressBar
from PyQt5.QtCore import Qt
from PyQt5.uic import loadUi
import epscalc
from pico3204D import Picoscope3204D


class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("epsdesign.ui", self)
        
        # Применяем стиль CSS
        self._apply_styles("epsdesign.css")
        
        # Инициализация прогресс-бара
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        
        # Остальная инициализация
        self._setup_ui()
        self._init_variables()

    def _apply_styles(self, stylesheet_path):
        try:
            with open(stylesheet_path, "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Ошибка загрузки стилей: {e}")

    def _setup_ui(self):
        self.cBox_conf.addItems(['1', '2', '3'])
        self.pBtn_start.clicked.connect(self.start)
        self.pBtn_save.clicked.connect(self.save)
        self.graphWidget.setBackground('w')

    def _init_variables(self):
        self.picoscope = None
        self.data = None
        self.Bmax = None
        self.H = None
        self.B = None
        self.powerLosses = None
        self.amp = 500000
        self.freq = None

    def _update_progress(self, value, message=None):
        """Обновление прогресс-бара и статуса"""
        self.progress_bar.setValue(value)
        if message:
            self.statusBar().showMessage(message)
        QApplication.processEvents()  # Обновляем GUI

    def init_pico(self):
        try:
            self.picoscope = Picoscope3204D()
            self.picoscope.initialize_ports()
            return True
        except Exception as e:
            print(f"Ошибка инициализации Picoscope: {e}")
            return False

    def _parse_input_values(self):
        try:
            self.freq = int(self.lEd_f.text().replace(',', '.'))
            B_target = float(self.lEd_B.text().replace(',', '.'))
            config_number = int(self.cBox_conf.currentText())
            
            x = float(self.lEd_x.text().replace(',', '.')) / 1000
            y = float(self.lEd_y.text().replace(',', '.')) / 1000
            N = int(self.lEd_N.text().replace(',', '.'))
            ro = float(self.lEd_ro.text().replace(',', '.'))
            
            return {
                'freq': self.freq,
                'B_target': B_target,
                'config_number': config_number,
                'sample_params': [x, y, N, ro],
                'timebase': 1252
            }
        except ValueError as e:
            print(f"Ошибка ввода данных: {e}")
            return None

    def _measure_until_target(self, params):
        """Цикл измерений с отображением прогресса"""
        max_attempts = 15  # (2000000-500000)/100000
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, max_attempts)
        
        key = False
        attempt = 0
        
        while not key and self.amp < 2000000:
            attempt += 1
            self._update_progress(
                attempt,
                f"Поиск амплитуды: попытка {attempt}/{max_attempts}"
            )
            
            self.amp += 100000
            self.picoscope.setup_generator(params['freq'], amplitude=self.amp)
            
            samples = int(5 * 100000 / params['freq'])
            self.data = self.picoscope.read_data(
                max_samples=samples,
                sample_rate=params['timebase']
            )
            
            run_parameters = [
                self.data,
                params['freq'],
                key,
                params['config_number'],
                params['sample_params']
            ]
            
            result = epscalc.run(run_parameters)
            Bmax = result[0]
            
            print(f"Текущая индукция: {Bmax} Тл")
            if Bmax >= params['B_target']:
                key = True
        
        self.progress_bar.setVisible(False)
        return key

    def _perform_final_measurement(self, params):
        """Финальное измерение с прогрессом"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        
        # Имитация прогресса (можно адаптировать под реальные шаги)
        for i in range(1, 101):
            self._update_progress(i, f"Финальное измерение: {i}%")
            # Здесь должна быть реальная логика измерения
            
        self.picoscope.setup_generator(params['freq'], amplitude=self.amp)
        samples = int(30 * 100000 / params['freq'])
        self.data = self.picoscope.read_data(
            max_samples=samples,
            sample_rate=params['timebase']
        )
        
        run_parameters = [
            self.data,
            params['freq'],
            True,
            params['config_number'],
            params['sample_params']
        ]
        
        result = epscalc.run(run_parameters)
        self.Bmax = result[0]
        self.H = result[1]
        self.B = result[2]
        self.powerLosses = result[3]
        
        self.progress_bar.setVisible(False)
        print(f"Финальные результаты - Bmax: {self.Bmax} Тл, Потери: {self.powerLosses} Вт/кг")

    def start(self):
        if not self.picoscope:
            print("Ошибка: Picoscope не инициализирован")
            return
        
        print("Начало измерений")
        
        params = self._parse_input_values()
        if not params:
            return
        
        try:
            # Блокируем кнопки во время измерений
            self.pBtn_start.setEnabled(False)
            self.pBtn_save.setEnabled(False)
            
            target_reached = self._measure_until_target(params)
            
            if not target_reached:
                print("Не удалось достичь целевой индукции")
                return
            
            self._perform_final_measurement(params)
            self.plotData()
            
        except Exception as e:
            print(f"Ошибка в процессе измерений: {e}")
        finally:
            # Разблокируем кнопки
            self.pBtn_start.setEnabled(True)
            self.pBtn_save.setEnabled(True)
            self.progress_bar.setVisible(False)

    def save(self):
        if not self.data or not self.picoscope:
            print("Нет данных для сохранения")
            return
            
        try:
            self.picoscope.save_data(self.data, self.freq, self.amp)
            print("Результаты успешно сохранены")
        except Exception as e:
            print(f"Ошибка при сохранении: {e}")

    def plotData(self):
        if not self.H or not self.B:
            print("Нет данных для построения графика")
            return
            
        self.graphWidget.clear()
        styles = {'color': 'black', 'font-size': '12px'}
        self.graphWidget.setLabel('left', "B (Тл)", **styles)
        self.graphWidget.setLabel('bottom', "H (А/м)", **styles)
        self.graphWidget.showGrid(x=True, y=True)
        self.graphWidget.setXRange(min(self.H), max(self.H))
        self.graphWidget.setYRange(min(self.B), max(self.B))
        self.graphWidget.plot(x=self.H, y=self.B, pen='b')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    try:
        epstein = MainUI()
        epstein.show()
        
        if not epstein.init_pico():
            sys.exit(1)
            
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        
    finally:
        if hasattr(epstein, 'picoscope') and epstein.picoscope:
            epstein.picoscope.close()
            print("Picoscope успешно закрыт")